# Architecture

```mermaid
graph TD
    subgraph Local Machine
        A[Your Markdown Docs] -->|python3 index.py| B[Indexer\nsrc/indexer.py]
        B -->|header-aware chunking\n400 words, 50 overlap| C[Chunks]
        C -->|sentence-transformers\nall-MiniLM-L6-v2| D[Embeddings]
        D --> E[(ChromaDB\n~/.mcp-kb/chroma)]
        F[MCP Server\nsrc/server.py] -->|search query| G[Searcher\nsrc/searcher.py]
        G -->|embed query| H[SentenceTransformer]
        H --> G
        G -->|vector query| E
        E -->|top-5 chunks + metadata| G
        G -->|citations| F
        F <-->|stdio JSON-RPC| I[Claude Desktop]
    end
    subgraph Optional Observability
        F -->|PHOENIX_ENABLED=1| J[Arize Phoenix\nlocalhost:6006]
    end
    subgraph Eval
        K[eval.py\n20 gold questions] -->|Recall@5, MRR| G
    end
```

## Components

| Component | File | Responsibility |
|-----------|------|----------------|
| Indexer | `src/indexer.py` | Chunk docs (header-aware) → embed → store in ChromaDB |
| Searcher | `src/searcher.py` | Embed query → vector search → format citations |
| Server | `src/server.py` | MCP stdio transport, exposes `search_docs` and `list_docs` |
| Config | `src/config.py` | Settings dataclass (paths, model name, chunk params) |
| Tracing | `src/tracing.py` | Optional Arize Phoenix span wrapper (no-op when disabled) |
| CLI | `index.py` | One-shot indexing command |
| Eval | `eval.py` | Recall@5 / MRR against 20 gold questions |

## Data flow

1. **Index time:** docs → chunk (header-aware) → embed → ChromaDB on disk
2. **Query time:** query → embed → ChromaDB vector search → top-5 chunks → citation format → MCP response
3. **Eval time:** gold questions → searcher → Recall@5, MRR printed to stdout
