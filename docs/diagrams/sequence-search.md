# Search Query Sequence

```mermaid
sequenceDiagram
    actor User
    participant CD as Claude Desktop
    participant MCP as MCP Server (server.py)
    participant S as Searcher (searcher.py)
    participant ST as SentenceTransformer
    participant DB as ChromaDB
    participant PX as Arize Phoenix (optional)

    User->>CD: "How do I roll back a deployment?"
    CD->>MCP: tools/call search_docs {query: "..."}
    MCP->>S: search(query, settings)
    Note over S: search_span context manager<br/>records span if PHOENIX_ENABLED=1
    S->>ST: encode(query) → 384-dim vector
    ST-->>S: query_embedding
    S->>DB: collection.query(embedding, n_results=5)
    DB-->>S: top-5 chunks + metadata [{text, source, start_line, end_line}]
    S-->>S: format citations "[source: runbook.md:L8-L14]"
    S--)PX: span.record_results(chunks) — if tracing on
    S-->>MCP: [{text, source, citation}, ...]
    MCP-->>CD: "[source: deployment-runbook.md:L8-L14]\nRun ./scripts/rollback.sh <sha>..."
    CD-->>User: Answer with cited sources
```

## Key design decisions

- **stdio transport**: MCP server communicates over stdin/stdout — zero network setup, works natively with Claude Desktop
- **Citation format**: `[source: filename.md:L42-L58]` is included in every result so Claude can include it in its answer
- **Top-5 retrieval**: ChromaDB returns 5 chunks; Claude sees all and synthesizes
- **Optional tracing**: `search_span` is a no-op context manager unless `PHOENIX_ENABLED=1` — zero overhead by default
