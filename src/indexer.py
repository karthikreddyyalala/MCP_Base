from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from src.config import Settings


def chunk_markdown(text: str, chunk_size: int = 400, chunk_overlap: int = 50) -> list[dict]:
    """Split text into overlapping chunks, tracking approximate line numbers."""
    words = text.split()
    if not words:
        return []

    lines = text.splitlines()
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text = " ".join(words[start:end])

        # Approximate line numbers by scanning accumulated word counts
        start_line, end_line = 1, len(lines)
        accumulated = 0
        found_start = False
        for i, line in enumerate(lines):
            accumulated += len(line.split())
            if not found_start and accumulated >= start:
                start_line = i + 1
                found_start = True
            if accumulated >= end:
                end_line = i + 1
                break

        chunks.append({"text": chunk_text, "start_line": start_line, "end_line": end_line})

        if end == len(words):
            break
        start = end - chunk_overlap

    return chunks


def build_index(settings: Settings) -> int:
    """Index all .md files under settings.docs_path. Returns total chunk count."""
    settings.db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.db_path))
    ef = SentenceTransformerEmbeddingFunction(model_name=settings.model_name)

    try:
        client.delete_collection("kb_docs")
    except Exception:
        pass
    col = client.create_collection("kb_docs", embedding_function=ef)

    docs, metas, ids = [], [], []
    chunk_id = 0

    for md_file in sorted(settings.docs_path.glob("**/*.md")):
        text = md_file.read_text(encoding="utf-8")
        for chunk in chunk_markdown(text, settings.chunk_size, settings.chunk_overlap):
            docs.append(chunk["text"])
            metas.append({"source": md_file.name, "start_line": chunk["start_line"], "end_line": chunk["end_line"]})
            ids.append(f"chunk_{chunk_id}")
            chunk_id += 1

    if docs:
        col.add(documents=docs, metadatas=metas, ids=ids)

    return len(docs)
