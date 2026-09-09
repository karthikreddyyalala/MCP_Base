import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from src.config import Settings


def _get_collection(settings: Settings):
    client = chromadb.PersistentClient(path=str(settings.db_path))
    ef = SentenceTransformerEmbeddingFunction(model_name=settings.model_name)
    return client.get_collection("kb_docs", embedding_function=ef)


def search(query: str, settings: Settings) -> list[dict]:
    """Return top-k chunks with citation strings."""
    col = _get_collection(settings)
    results = col.query(query_texts=[query], n_results=settings.top_k, include=["documents", "metadatas"])
    output = []
    for text, meta in zip(results["documents"][0], results["metadatas"][0]):
        citation = f"[source: {meta['source']}:L{meta['start_line']}-L{meta['end_line']}]"
        output.append({"text": text, "source": meta["source"], "citation": citation})
    return output


def list_sources(settings: Settings) -> list[str]:
    """Return sorted unique filenames in the index."""
    col = _get_collection(settings)
    all_meta = col.get(include=["metadatas"])["metadatas"]
    return sorted({m["source"] for m in all_meta})
