"""
MS MARCO Passage Ranking — MRR@10 benchmark.

Uses ir_datasets to stream the 8.8M passage corpus, reservoir-samples 1.1M
passages (always including all qrel-relevant passages), embeds with
all-MiniLM-L6-v2, and indexes with FAISS for fast ANN search.

Usage:
    pip install ir_datasets faiss-cpu
    PYTHONPATH=. python3 scripts/eval_msmarco.py            # full 1.1M run (~90 min)
    PYTHONPATH=. python3 scripts/eval_msmarco.py --smoke    # quick end-to-end test
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

MODEL_NAME = "all-MiniLM-L6-v2"
DIM = 384
EMBED_BATCH = 512
TOP_K = 10
BM25_BASELINE = 0.167


def load_qrels_and_queries():
    import urllib.request, csv, io
    import ir_datasets

    # qrels from HuggingFace (Microsoft's qrels.dev.small.tsv is 404)
    print("Loading qrels...")
    url = "https://huggingface.co/datasets/BeIR/msmarco-qrels/resolve/main/dev.tsv"
    with urllib.request.urlopen(url) as r:
        data = r.read().decode()
    qrels: dict[str, set[str]] = defaultdict(set)
    relevant_pids: set[str] = set()
    for row in csv.reader(io.StringIO(data), delimiter="\t"):
        if len(row) == 3:
            qid, pid, score = row       # BeIR format: qid pid score
        elif len(row) >= 4:
            qid, _, pid, score = row[0], row[1], row[2], row[3]  # TREC format: qid iter pid rel
        else:
            continue
        if not score.lstrip("-").isdigit():
            continue
        if int(score) > 0:
            qrels[qid].add(pid)
            relevant_pids.add(pid)
    print(f"  {len(qrels):,} queries | {len(relevant_pids):,} unique relevant passages")

    # queries from ir_datasets (already cached in collectionandqueries.tar)
    print("Loading queries...")
    dataset = ir_datasets.load("msmarco-passage/dev/small")
    queries = {q.query_id: q.text for q in dataset.queries_iter() if q.query_id in qrels}
    print(f"  {len(queries):,} queries loaded")

    return dict(qrels), relevant_pids, queries


def reservoir_sample(n_target: int, relevant_pids: set[str], smoke: bool) -> dict[str, str]:
    import ir_datasets
    corpus = ir_datasets.load("msmarco-passage")

    n_fill = n_target - len(relevant_pids)
    kept: dict[str, str] = {}
    reservoir: list[tuple[str, str]] = []
    n_seen_fill = 0

    print("Streaming corpus via ir_datasets...")
    for doc in tqdm(corpus.docs_iter(), total=8_841_823, desc="Sampling", unit="passages"):
        pid, text = doc.doc_id, doc.text[:512]
        if pid in relevant_pids:
            kept[pid] = text
            continue
        n_seen_fill += 1
        if len(reservoir) < n_fill:
            reservoir.append((pid, text))
        else:
            j = random.randint(0, n_seen_fill - 1)
            if j < n_fill:
                reservoir[j] = (pid, text)
        if smoke and n_seen_fill >= 200_000:
            break

    for pid, text in reservoir:
        kept[pid] = text
    print(f"  Sampled {len(kept):,} passages ({len(relevant_pids):,} relevant + {len(reservoir):,} fill)")
    return kept


def build_or_load_index(index_dir: str, passages: dict[str, str]) -> tuple[faiss.Index, list[str]]:
    path = Path(index_dir)
    index_file = path / "index.faiss"
    ids_file = path / "ids.json"

    if index_file.exists() and ids_file.exists():
        pid_list = json.loads(ids_file.read_text())
        if len(pid_list) >= len(passages):
            print(f"Cached FAISS index: {len(pid_list):,} passages. Loading...")
            index = faiss.read_index(str(index_file))
            return index, pid_list
        print(f"Cached index has {len(pid_list):,} passages — rebuilding.")

    path.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(MODEL_NAME)
    pid_list = list(passages.keys())
    texts = [passages[pid] for pid in pid_list]

    print(f"\nEmbedding {len(texts):,} passages with {MODEL_NAME}...")
    all_vecs: list[np.ndarray] = []
    for start in tqdm(range(0, len(texts), EMBED_BATCH), desc="Embedding", unit="batch"):
        vecs = model.encode(texts[start : start + EMBED_BATCH], show_progress_bar=False, convert_to_numpy=True)
        all_vecs.append(vecs.astype(np.float32))

    matrix = np.vstack(all_vecs)
    faiss.normalize_L2(matrix)

    index = faiss.IndexFlatIP(DIM)
    index.add(matrix)
    faiss.write_index(index, str(index_file))
    ids_file.write_text(json.dumps(pid_list))
    print(f"Saved FAISS index: {index.ntotal:,} passages → {index_dir}\n")
    return index, pid_list


def eval_mrr(
    index: faiss.Index,
    pid_list: list[str],
    qrels: dict[str, set[str]],
    queries: dict[str, str],
    n_queries: int | None,
) -> tuple[float, int]:
    model = SentenceTransformer(MODEL_NAME)
    query_items = list(queries.items())
    if n_queries:
        query_items = query_items[:n_queries]

    print(f"Evaluating {len(query_items):,} queries...\n")
    mrr_sum = 0.0
    for qid, qtext in tqdm(query_items, desc="Querying", unit="q"):
        qvec = model.encode([qtext], convert_to_numpy=True).astype(np.float32)
        faiss.normalize_L2(qvec)
        _, idxs = index.search(qvec, TOP_K)
        relevant = qrels.get(qid, set())
        for rank, idx in enumerate(idxs[0], 1):
            if idx >= 0 and pid_list[idx] in relevant:
                mrr_sum += 1.0 / rank
                break

    return mrr_sum / len(query_items), len(query_items)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-dir", default="~/.mcp-kb/msmarco-faiss")
    parser.add_argument("--passages", type=int, default=1_100_000)
    parser.add_argument("--queries", type=int, default=None)
    parser.add_argument("--smoke", action="store_true", help="~210K corpus scan, 50 queries")
    args = parser.parse_args()

    if args.smoke:
        args.passages = 10_000
        args.queries = 50

    random.seed(42)
    index_dir = str(Path(args.index_dir).expanduser())

    qrels, relevant_pids, queries = load_qrels_and_queries()
    passages = reservoir_sample(args.passages, relevant_pids, smoke=args.smoke)
    index, pid_list = build_or_load_index(index_dir, passages)
    mrr, n_queries = eval_mrr(index, pid_list, qrels, queries, args.queries)

    bar = "─" * 46
    print(f"\n{bar}")
    print(f"  Benchmark   MS MARCO Passage Ranking (dev)")
    print(f"  Corpus      {index.ntotal:,} passages (reservoir-sampled)")
    print(f"  Queries     {n_queries:,}")
    print(f"  Metric      MRR@{TOP_K}")
    print(bar)
    print(f"  Score       {mrr:.3f}")
    print(f"  BM25 base   {BM25_BASELINE:.3f}")
    print(f"  vs baseline {mrr / BM25_BASELINE:.1f}x")
    print(f"{bar}\n")


if __name__ == "__main__":
    main()
