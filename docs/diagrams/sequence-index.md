# Indexing Sequence

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CLI as index.py (typer CLI)
    participant IDX as Indexer (indexer.py)
    participant ST as SentenceTransformer
    participant DB as ChromaDB (~/.mcp-kb/chroma)

    Dev->>CLI: python3 index.py --docs ./example-docs
    CLI->>IDX: build_index(Settings(docs_path, db_path))
    IDX->>DB: delete_collection("kb_docs") — fresh rebuild
    IDX->>DB: create_collection("kb_docs", embedding_function=ST)

    loop Each *.md file (sorted)
        IDX->>IDX: read_text(encoding="utf-8")
        IDX->>IDX: chunk_markdown(text, chunk_size=400, overlap=50)
        Note over IDX: header-aware splitting:<br/>1. Split at ## headings into sections<br/>2. Word-split within each section<br/>3. Prefix each chunk with its heading
        IDX->>ST: batch embed chunk texts
        ST-->>IDX: embeddings[]
        IDX->>IDX: accumulate docs[], metadatas[], ids[]
    end

    IDX->>DB: collection.add(documents, embeddings, metadatas, ids)
    DB-->>IDX: stored
    IDX-->>CLI: chunk_count (e.g. 9)
    CLI-->>Dev: "Done. Indexed 9 chunks from example-docs"
```

## Chunk metadata stored per chunk

| Field | Example | Purpose |
|-------|---------|---------|
| `source` | `deployment-runbook.md` | File-level attribution |
| `start_line` | `8` | Start of chunk in source file |
| `end_line` | `14` | End of chunk — forms `L8-L14` citation |

## Header-aware chunking example

Input:
```markdown
## Rollback Procedure

If error rate spikes, run rollback: ./scripts/rollback.sh <sha>
Takes ~3 minutes. Notify #incidents in Slack.
```

Output chunk:
```
## Rollback Procedure

If error rate spikes, run rollback: ./scripts/rollback.sh <sha> Takes ~3 minutes. Notify #incidents in Slack.
```

Without the header prefix, a chunk starting mid-section would lose all section context.
