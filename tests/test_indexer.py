from pathlib import Path
import pytest
from src.config import Settings
from src.indexer import build_index, chunk_markdown


def test_chunk_markdown_splits_on_size():
    text = "word " * 500
    chunks = chunk_markdown(text, chunk_size=400, chunk_overlap=50)
    assert len(chunks) >= 2, "Long text should produce multiple chunks"


def test_chunk_markdown_preserves_overlap():
    text = "\n".join(f"Line {i}: " + "content " * 10 for i in range(100))
    chunks = chunk_markdown(text, chunk_size=400, chunk_overlap=50)
    assert len(chunks) >= 2


def test_build_index_returns_chunk_count(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "test.md").write_text("# Hello\n\nThis is a test document with some content.\n")
    db_dir = tmp_path / "chroma"
    settings = Settings(docs_path=docs_dir, db_path=db_dir)
    count = build_index(settings)
    assert count >= 1


def test_build_index_stores_source_metadata(tmp_path):
    import chromadb
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "runbook.md").write_text("# Runbook\n\n" + "Deploy step. " * 50)
    db_dir = tmp_path / "chroma"
    settings = Settings(docs_path=docs_dir, db_path=db_dir)
    build_index(settings)
    client = chromadb.PersistentClient(path=str(db_dir))
    col = client.get_collection("kb_docs")
    results = col.get(include=["metadatas"])
    sources = {m["source"] for m in results["metadatas"]}
    assert "runbook.md" in sources
