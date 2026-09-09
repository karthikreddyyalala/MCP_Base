# Morning Test Guide

Everything to verify the project works end-to-end. Run in order.

---

## 1. Install dependencies (first time only)

```bash
cd /Users/jaipal/claude-code/mcp-knowledge-base
pip install -e ".[dev]"
```

---

## 2. Run the test suite

```bash
pytest tests/ -v
```

**Expected:** `10 passed`

Tests cover: header-aware chunking, naive chunking, overlap, chunk count, source metadata, search results, citation format, citation presence, source listing.

---

## 3. Index the example docs

```bash
PYTHONPATH=. python3 index.py --docs ./example-docs
```

**Expected output:**
```
Indexing docs from: example-docs
Done. Indexed 9 chunks from example-docs
```

---

## 4. Run the retrieval eval

```bash
PYTHONPATH=. python3 eval.py --docs ./example-docs
```

**Expected:**
```
Metric             Value
-------------------------
Recall@5           1.000  (20/20)
MRR                0.925

Gold set: 20 questions across 3 docs
```

Recall@5 ≥ 0.80 and MRR ≥ 0.70 = healthy. Perfect score = header-aware chunker is working.

---

## 5. Smoke-test the MCP server

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' \
  | PYTHONPATH=. python3 src/server.py 2>/dev/null
```

**Expected:** Two JSON blobs — second one lists `search_docs` and `list_docs` tools.

---

## 6. Test in Claude Desktop

1. Open Claude Desktop
2. Go to **Settings → Developer** — verify `knowledge-base` shows **Running**
3. In a new chat, type exactly:

   > *Use the knowledge-base tool to search: how do I roll back a deployment?*

4. **Expected:** Response includes `[source: deployment-runbook.md:L8-L14]` and mentions `./scripts/rollback.sh`

---

## 7. Optional: Phoenix tracing

```bash
pip install -e ".[tracing]"

# Terminal 1
python3 -m phoenix.server.main serve
# Opens http://localhost:6006

# Terminal 2
PHOENIX_ENABLED=1 PYTHONPATH=. python3 src/server.py
```

Ask Claude Desktop a question — the retrieval span appears at http://localhost:6006 with query text and retrieved sources logged.

---

## What was built overnight

| Feature | Files | Signal |
|---------|-------|--------|
| CI badge (GitHub Actions) | `.github/workflows/tests.yml` | Ships like a professional |
| Header-aware chunker | `src/indexer.py` | Understands document structure |
| Retrieval eval (Recall@5, MRR) | `eval.py` | Measures what you ship |
| Architecture diagram | `docs/diagrams/architecture.md` | Explains the system visually |
| Search sequence diagram | `docs/diagrams/sequence-search.md` | Shows query flow end-to-end |
| Index sequence diagram | `docs/diagrams/sequence-index.md` | Shows indexing pipeline |
| Phoenix observability | `src/tracing.py` | Production-grade thinking |

---

## Talking points for recruiters / interviews

- **MCP server authorship** — built from scratch with Anthropic's official SDK; shows up as a live tool in Claude Desktop
- **RAG pipeline** — embedding, header-aware chunking, retrieval with line-range citations
- **Eval mindset** — Recall@5 / MRR over 20 gold questions; chose IR metrics over RAGAS because this is a retriever, not a generator (shows judgment, not just framework use)
- **Observability** — Arize Phoenix integration (used at Replit, Harvey); knows production RAG needs tracing
- **Local-first** — zero external accounts, `pip install` and go; ChromaDB + sentence-transformers run fully offline

---

## Quick reference — useful commands

```bash
# Re-index
PYTHONPATH=. python3 index.py --docs ./example-docs

# Eval
PYTHONPATH=. python3 eval.py --docs ./example-docs

# Run tests
pytest tests/ -v

# Start server manually (for debugging)
PYTHONPATH=. python3 src/server.py

# Index custom docs
PYTHONPATH=. python3 index.py --docs /path/to/your/docs --db /path/to/store/vectors
```
