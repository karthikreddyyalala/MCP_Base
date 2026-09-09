# MCP Knowledge Base

> MCP server that turns any folder of markdown docs into a searchable knowledge base for Claude Desktop and Cursor.  
> Deploy in 5 minutes. Works with any MCP client. Zero external accounts.

---

## How it works

```
your-docs/          ← any folder of .md files
     │
     ▼
python3 index.py --docs ./your-docs
     │  chunks markdown → embeds with all-MiniLM-L6-v2 (local, offline)
     ▼
~/.mcp-kb/chroma/   ← vector store lives on disk
     │
     ▼
python3 src/server.py   ← MCP server (stdio transport)
     │
     ├─ search_docs("how to rollback?")
     │      → top-5 chunks + [source: runbook.md:L18-L24]
     │
     └─ list_docs()
            → "Indexed: onboarding.md, runbook.md, api-reference.md"
```

1. Run `index.py` once — chunks your `.md` files and stores vectors locally (ChromaDB).
2. The MCP server loads that index on startup.
3. Claude gets two tools: **`search_docs`** (semantic search with cited answers) and **`list_docs`** (see what's indexed).

---

## Quickstart

```bash
git clone https://github.com/karthikreddyyalala/MCP_Base.git
cd MCP_Base
pip install -e .

# Index the example docs (run once; re-run when your docs change)
python3 index.py --docs ./example-docs

# Verify the server responds
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}\n' \
  | PYTHONPATH=. python3 src/server.py
```

---

## Connect to Claude Desktop

Add this block to `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "knowledge-base": {
      "command": "python3",
      "args": ["/absolute/path/to/MCP_Base/src/server.py"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/MCP_Base",
        "KB_DOCS_PATH": "/absolute/path/to/your/docs",
        "KB_DB_PATH": "/Users/yourname/.mcp-kb/chroma"
      }
    }
  }
}
```

Restart Claude Desktop. Try:
- *"What docs do you have access to?"*
- *"How do I roll back a deployment?"*
- *"What authentication does the API use?"*

---

## Example output

```
[source: deployment-runbook.md:L8-L14]
If error rate spikes, run rollback: ./scripts/rollback.sh <previous-sha>
This redeploys the previous image tag. Takes ~3 minutes. Notify #incidents in Slack.
```

---

## Tools exposed

| Tool | Input | Returns |
|------|-------|---------|
| `search_docs(query)` | Natural language question | Top-5 chunks with `[source: file.md:L42-L58]` citations |
| `list_docs()` | — | Sorted list of indexed markdown filenames |

---

## Stack

| Component | Library | Why |
|-----------|---------|-----|
| MCP server | [`mcp`](https://github.com/anthropics/mcp) | Official Anthropic SDK — stdio transport |
| Vector store | [`chromadb`](https://www.trychroma.com/) | Local, no account needed |
| Embeddings | [`sentence-transformers`](https://www.sbert.net/) `all-MiniLM-L6-v2` | Runs fully offline after first download |
| CLI | [`typer`](https://typer.tiangolo.com/) | Clean `--docs` / `--db` flags |

---

## Indexing your own docs

```bash
python3 index.py --docs /path/to/your/docs --db /path/to/store/vectors
```

Point `KB_DOCS_PATH` and `KB_DB_PATH` in the Claude Desktop config to the same paths. Re-run `index.py` whenever your docs change.

---

## Running tests

```bash
pytest tests/ -v
```
