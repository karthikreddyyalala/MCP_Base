"""
MS MARCO Passage Ranking — MRR@10 benchmark.

Streams the 8.8M passage corpus once to reservoir-sample 1.1M passages that
ALWAYS include all qrel-relevant passages (so MRR@10 is accurate, not deflated
by a naive head-of-corpus slice). Indexes into a dedicated ChromaDB collection.
Subsequent runs reuse the cached index.

Usage:
    pip install datasets tqdm
    PYTHONPATH=. python3 scripts/eval_msmarco.py            # full 1.1M run
    PYTHONPATH=. python3 scripts/eval_msmarco.py --smoke    # 10K passages, 50 queries
"""

import argparse
import random
from collections import defaultdict
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from tqdm import tqdm

COLLECTION = "msmarco_eval"
MODEL = "all-MiniLM-L6-v2"
INDEX_BATCH = 256
TOP_K = 10
BM25_BASELINE = 0.167


# ── data loading ────────────────────────────────────────────────────────────

def load_qrels() -> tuple[dict[str, set[str]], set[str]]:
    """Returns ({qid: {relevant_passage_ids}}, set_of_all_relevant_pids)."""
    from datasets import load_dataset

    print("Loading qrels (validation split)...")
    rows = load_dataset("BeIR/msmarco-qrels", split="validation")
    qrels: dict[str, set[str]] = defaultdict(set)
    relevant_pids: set[str] = set()
    for row in rows:
        if int(row["score"]) > 0:
            pid = str(row["corpus-id"])
            qrels[str(row["query-id"])].add(pid)
            relevant_pids.add(pid)
    print(f"  {len(qrels):,} queries | {len(relevant_pids):,} unique relevant passages")
    return dict(qrels), relevant_pids


def reservoir_sample(
    n_target: int, relevant_pids: set[str], smoke: bool
) -> dict[str, str]:
    """
    Stream corpus once. Always keep relevant passages. Reservoir-sample the
    rest until we reach n_target total. Returns {passage_id: text}.

    ponytail: O(N) stream over 8.8M rows is the only correct approach here —
    relevant passages are spread 0..8M so any head-slice misses almost all of them.
    """
    from datasets import load_dataset

    n_fill = n_target - len(relevant_pids)
    assert n_fill > 0, "n_target must exceed number of relevant passages"

    corpus = load_dataset(
        "BeIR/msmarco", "corpus", split="corpus", streaming=True
    )

    kept: dict[str, str] = {}       # pid → text (relevant passages, always kept)
    reservoir: list[tuple[str, str]] = []  # random fill passages
    n_seen_fill = 0                 # non-relevant passages seen so far

    total_hint = 8_841_823

    for row in tqdm(corpus, total=total_hint, desc="Sampling corpus", unit="passages"):
        pid = str(row["_id"])
        text = row["text"][:512]    # MiniLM practical context

        if pid in relevant_pids:
            kept[pid] = text
            continue

        # Reservoir sampling for fill passages
        n_seen_fill += 1
        if len(reservoir) < n_fill:
            reservoir.append((pid, text))
        else:
            j = random.randint(0, n_seen_fill - 1)
            if j < n_fill:
                reservoir[j] = (pid, text)

        if not smoke and n_seen_fill > 50_000_000:
            break  # safety cap

    for pid, text in reservoir:
        kept[pid] = text

    return kept


# ── index ────────────────────────────────────────────────────────────────────

def get_collection(db_path: str):
    client = chromadb.PersistentClient(path=db_path)
    ef = SentenceTransformerEmbeddingFunction(model_name=MODEL)
    return client, ef


def build_index(
    db_path: str, passages: dict[str, str]
) -> chromadb.Collection:
    client, ef = get_collection(db_path)

    try:
        col = client.get_collection(COLLECTION, embedding_function=ef)
        if col.count() >= len(passages):
            print(f"Cached index: {col.count():,} passages. Skipping rebuild.")
            return col
        print(f"Cached index has {col.count():,} passages — rebuilding.")
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    col = client.create_collection(COLLECTION, embedding_function=ef)

    items = list(passages.items())
    print(f"\nIndexing {len(items):,} passages...")
    for start in tqdm(range(0, len(items), INDEX_BATCH), desc="Embedding", unit="batch"):
        batch = items[start : start + INDEX_BATCH]
        pids = [pid for pid, _ in batch]
        texts = [text for _, text in batch]
        col.add(documents=texts, ids=pids)

    print(f"Indexed {col.count():,} passages.\n")
    return col


# ── eval ─────────────────────────────────────────────────────────────────────

def eval_mrr(
    col: chromadb.Collection,
    qrels: dict[str, set[str]],
    n_queries: int | None,
) -> tuple[float, int]:
    from datasets import load_dataset

    print("Loading queries...")
    query_rows = load_dataset("BeIR/msmarco", "queries", split="queries")

    queries = [
        (str(row["_id"]), row["text"])
        for row in query_rows
        if str(row["_id"]) in qrels
    ]
    if n_queries:
        queries = queries[:n_queries]

    print(f"Evaluating {len(queries):,} queries...\n")
    mrr_sum = 0.0
    for qid, qtext in tqdm(queries, desc="Querying", unit="q"):
        results = col.query(query_texts=[qtext], n_results=TOP_K)
        for rank, pid in enumerate(results["ids"][0], 1):
            if pid in qrels.get(qid, set()):
                mrr_sum += 1.0 / rank
                break

    return mrr_sum / len(queries), len(queries)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="~/.mcp-kb/msmarco", help="ChromaDB path")
    parser.add_argument("--passages", type=int, default=1_100_000)
    parser.add_argument("--queries", type=int, default=None, help="Cap queries for testing")
    parser.add_argument(
        "--smoke", action="store_true",
        help="Quick smoke test: 10K sample passages, 50 queries"
    )
    args = parser.parse_args()

    if args.smoke:
        args.passages = 10_000
        args.queries = 50

    random.seed(42)
    db_path = str(Path(args.db).expanduser())

    qrels, relevant_pids = load_qrels()
    passages = reservoir_sample(args.passages, relevant_pids, smoke=args.smoke)
    col = build_index(db_path, passages)
    mrr, n_queries = eval_mrr(col, qrels, args.queries)

    bar = "─" * 46
    print(f"\n{bar}")
    print(f"  Benchmark   MS MARCO Passage Ranking (dev)")
    print(f"  Corpus      {col.count():,} passages (reservoir-sampled)")
    print(f"  Queries     {n_queries:,}")
    print(f"  Metric      MRR@{TOP_K}")
    print(bar)
    print(f"  Score       {mrr:.3f}")
    print(f"  BM25 base   {BM25_BASELINE:.3f}")
    print(f"  vs baseline {mrr / BM25_BASELINE:.1f}x")
    print(f"{bar}\n")


if __name__ == "__main__":
    main()
