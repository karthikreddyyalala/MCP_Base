# MCP Knowledge Base

Every company has internal docs — runbooks, onboarding guides, API references — sitting in a folder somewhere, completely invisible to the AI tools their teams use every day. This project fixes that.

It's an MCP server that indexes a folder of markdown files and gives Claude Desktop (or any MCP client) two tools: one to search those docs semantically, one to list what's available. Answers come with exact citations — `[source: runbook.md:L18-L24]` — so you always know where the information came from.

No Pinecone account. No OpenAI key. No cloud infrastructure. Everything runs locally.

---

## Why I built this

Three job listings I was reading — Anthropic, DevRev, and ICON — all mentioned MCP in their requirements. Not as a nice-to-have. As a core skill.

I wanted to understand it from the inside, not just read the docs. So I picked a problem I kept hearing about in engineering teams: "we have all this internal documentation but our AI assistant doesn't know about it." Built the thing that solves it.

The interesting part wasn't wiring up the vector store. It was figuring out what makes a RAG system actually trustworthy — which is why every result includes a line number citation. A system that tells you something without telling you *where* it found it isn't useful in a professional context. You can't verify it, you can't trust it, you can't improve it.

---

## What it does

```
your-docs/            ← any folder of .md files
      │
      ▼
python3 index.py --docs ./your-docs
      │  chunks text → embeds with all-MiniLM-L6-v2 (offline)
      ▼
~/.mcp-kb/chroma/     ← vector store on disk
      │
      ▼
python3 src/server.py ← MCP server (stdio transport)
      │
      ├─ search_docs("how do I roll back?")
      │      → top-5 chunks + [source: runbook.md:L8-L14]
      │
      └─ list_docs()
             → "api-reference.md, deployment-runbook.md, onboarding.md"
```

Run the indexer once. Connect the server to Claude Desktop. Ask questions in plain English. Get cited answers from your actual documentation.

---

## Quickstart

```bash
git clone https://github.com/karthikreddyyalala/MCP_Base.git
cd MCP_Base
pip install -e .

# Index the included example docs
python3 index.py --docs ./example-docs

# Confirm the server starts and lists its tools
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}\n' \
  | PYTHONPATH=. python3 src/server.py
```

---

## Connect to Claude Desktop

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

Restart Claude Desktop. You'll see a hammer icon in the chat input — that's your knowledge base. Try:

- *"What docs do you have access to?"*
- *"How do I roll back a bad deployment?"*
- *"What authentication does the API require?"*

---

## Example output

```
[source: deployment-runbook.md:L8-L14]
If error rate spikes, run rollback: ./scripts/rollback.sh <previous-sha>
This redeploys the previous image tag. Takes ~3 minutes. Notify #incidents in Slack.
```

The citation tells you exactly where in the file that answer came from. You can verify it, share it, or update it.

---

## Tools

| Tool | What it does |
|------|-------------|
| `search_docs(query)` | Semantic search over indexed docs. Returns top-5 chunks with `[source: file.md:L42-L58]` citations. |
| `list_docs()` | Lists every markdown file currently in the index. |

---

## Technical decisions worth knowing about

**Why ChromaDB over Pinecone?** The README promise is "deploy in 5 minutes." Requiring a Pinecone signup breaks that. ChromaDB is a single pip install, stores vectors on disk, and needs no account. The right tool for local-first software.

**Why `all-MiniLM-L6-v2`?** It's 80MB, downloads once, runs fully offline after that, and produces strong semantic embeddings for English prose. For a knowledge base over internal documentation, it's more than sufficient.

**Why line-range citations?** A RAG system that tells you something without telling you where it came from is a liability. Line numbers mean you can open the source file, verify the answer, and notice when documentation is out of date.

**Why 400-token chunks with 50-token overlap?** Long enough to capture full thoughts, short enough to retrieve precisely. The overlap prevents context from being cut at chunk boundaries.

---

## Stack

| Component | Library |
|-----------|---------|
| MCP server | [`mcp`](https://github.com/anthropics/mcp) — Anthropic's official SDK |
| Vector store | [`chromadb`](https://www.trychroma.com/) — local, no account |
| Embeddings | [`sentence-transformers`](https://www.sbert.net/) `all-MiniLM-L6-v2` |
| CLI | [`typer`](https://typer.tiangolo.com/) |

---

## Using your own docs

```bash
python3 index.py --docs /path/to/your/docs --db /path/to/store/vectors
```

Update `KB_DOCS_PATH` and `KB_DB_PATH` in the Claude Desktop config to match. Re-run `index.py` whenever your docs change — it rebuilds the index from scratch each time.

---

## Tests

```bash
pytest tests/ -v
```

8 tests covering chunking logic, index construction, search result format, citation format, and source listing.
