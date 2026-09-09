# MCP Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local MCP server that indexes a folder of markdown docs and exposes `search_docs` and `list_docs` tools to any MCP client (Claude Desktop, Cursor).

**Architecture:** A Python MCP server reads a ChromaDB collection on startup (pre-built by a separate CLI indexer). The two MCP tools query that collection and return cited chunks (filename + line range). No external accounts, no cloud infra — clone and run.

**Tech Stack:** Python 3.11+, `mcp` SDK (official Anthropic), `chromadb`, `sentence-transformers` (all-MiniLM-L6-v2), `typer` (CLI), `pytest`

**Spec:** docs/superpowers/plans/2026-09-08-mcp-knowledge-base.md (self-contained)

## Global Constraints

- Python 3.11+ only
- No external API keys required
- All data stays local (`~/.mcp-kb/` by default)
- MCP transport: stdio (standard for Claude Desktop)
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (runs fully offline after first download)
- Top-k default: 5 chunks per search
- Chunk size: 400 tokens, 50-token overlap
- Citation format: `[source: filename.md:L42-L58]`

---

## File Structure

```
mcp-knowledge-base/
├── src/
│   ├── config.py          # Settings dataclass (docs_path, db_path, top_k)
│   ├── indexer.py         # Markdown chunking + ChromaDB ingestion
│   ├── searcher.py        # Semantic search + citation formatting
│   └── server.py          # MCP server, tool definitions
├── index.py               # CLI entry point (typer)
├── example-docs/
│   ├── onboarding.md
│   ├── deployment-runbook.md
│   └── api-reference.md
├── tests/
│   ├── test_indexer.py
│   └── test_searcher.py
├── pyproject.toml
└── README.md
```

---

### Task 1: Project scaffold + config

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: `Settings` dataclass with `docs_path: Path`, `db_path: Path`, `top_k: int = 5`, `model_name: str`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "mcp-knowledge-base"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",
    "chromadb>=0.5.0",
    "sentence-transformers>=3.0.0",
    "typer>=0.12.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create src/config.py**

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Settings:
    docs_path: Path
    db_path: Path = field(default_factory=lambda: Path.home() / ".mcp-kb" / "chroma")
    top_k: int = 5
    model_name: str = "all-MiniLM-L6-v2"
    chunk_size: int = 400
    chunk_overlap: int = 50
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 4: Verify install**

```bash
python -c "import mcp; import chromadb; import sentence_transformers; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml src/ tests/
git commit -m "feat: project scaffold and settings"
```

---

### Task 2: Markdown indexer

**Files:**
- Create: `src/indexer.py`
- Create: `tests/test_indexer.py`
- Create: `example-docs/onboarding.md` (sample fixture)

**Interfaces:**
- Consumes: `Settings` from `src/config.py`
- Produces:
  - `build_index(settings: Settings) -> int` — returns count of chunks indexed
  - ChromaDB collection named `"kb"` in `settings.db_path`
  - Each ChromaDB document has metadata: `{"source": "filename.md", "start_line": int, "end_line": int}`

- [ ] **Step 1: Create example-docs/onboarding.md**

```markdown
# Onboarding Guide

## Day 1

Welcome to the team. Your first task is to set up your local development environment.

Clone the main repo:
```bash
git clone https://github.com/acme/backend.git
```

## Access

Request access to AWS via the IT portal at https://it.acme.internal.
Your manager will approve within 24 hours.

## Tools

Install the following tools before your first standup:
- Docker Desktop
- VS Code with the Remote SSH extension
- 1Password (license in your welcome email)
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_indexer.py
from pathlib import Path
import pytest
import tempfile
from src.config import Settings
from src.indexer import build_index, chunk_markdown

def test_chunk_markdown_splits_on_size():
    text = "word " * 500  # 500 words, well over 400-token limit
    lines = text.splitlines(keepends=True) or [text]
    chunks = chunk_markdown(text, chunk_size=400, chunk_overlap=50)
    assert len(chunks) >= 2, "Long text should produce multiple chunks"

def test_chunk_markdown_preserves_overlap():
    text = "\n".join(f"Line {i}: " + "content " * 10 for i in range(100))
    chunks = chunk_markdown(text, chunk_size=400, chunk_overlap=50)
    # Last tokens of chunk N should appear at start of chunk N+1
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
    col = client.get_collection("kb")
    results = col.get(include=["metadatas"])
    sources = {m["source"] for m in results["metadatas"]}
    assert "runbook.md" in sources
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
pytest tests/test_indexer.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` for `src.indexer`

- [ ] **Step 4: Implement src/indexer.py**

```python
from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from src.config import Settings


def chunk_markdown(text: str, chunk_size: int = 400, chunk_overlap: int = 50) -> list[dict]:
    """Split text into overlapping chunks, tracking line numbers."""
    words = text.split()
    chunks = []
    lines = text.splitlines()

    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)

        # Approximate line numbers by searching for chunk start in original lines
        start_line = 1
        end_line = len(lines)
        accumulated = 0
        for i, line in enumerate(lines):
            accumulated += len(line.split())
            if accumulated >= start and start_line == 1:
                start_line = i + 1
            if accumulated >= end:
                end_line = i + 1
                break

        chunks.append({
            "text": chunk_text,
            "start_line": start_line,
            "end_line": end_line,
        })
        if end == len(words):
            break
        start = end - chunk_overlap

    return chunks


def build_index(settings: Settings) -> int:
    """Index all .md files in settings.docs_path. Returns total chunk count."""
    settings.db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.db_path))
    ef = SentenceTransformerEmbeddingFunction(model_name=settings.model_name)

    try:
        client.delete_collection("kb")
    except Exception:
        pass
    col = client.create_collection("kb", embedding_function=ef)

    docs, metas, ids = [], [], []
    chunk_id = 0

    for md_file in sorted(settings.docs_path.glob("**/*.md")):
        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_markdown(text, settings.chunk_size, settings.chunk_overlap)
        for chunk in chunks:
            docs.append(chunk["text"])
            metas.append({
                "source": md_file.name,
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
            })
            ids.append(f"chunk_{chunk_id}")
            chunk_id += 1

    if docs:
        col.add(documents=docs, metadatas=metas, ids=ids)

    return len(docs)
```

- [ ] **Step 5: Run tests — all must pass**

```bash
pytest tests/test_indexer.py -v
```
Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/indexer.py tests/test_indexer.py example-docs/
git commit -m "feat: markdown chunker and chromadb indexer"
```

---

### Task 3: Semantic searcher with citations

**Files:**
- Create: `src/searcher.py`
- Create: `tests/test_searcher.py`

**Interfaces:**
- Consumes: `Settings` from `src/config.py`, ChromaDB collection `"kb"` built by `build_index`
- Produces:
  - `search(query: str, settings: Settings) -> list[dict]` — each dict: `{"text": str, "source": str, "citation": str}`
  - `list_sources(settings: Settings) -> list[str]` — unique source filenames in the index
  - `citation` format: `"[source: filename.md:L42-L58]"`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_searcher.py
import pytest
from pathlib import Path
from src.config import Settings
from src.indexer import build_index
from src.searcher import search, list_sources

@pytest.fixture
def indexed_settings(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "deploy.md").write_text(
        "# Deployment\n\n"
        "To deploy the app run: kubectl apply -f k8s/\n\n"
        "Check pod status with: kubectl get pods\n\n" * 20
    )
    (docs_dir / "onboarding.md").write_text(
        "# Onboarding\n\nClone the repo and run npm install.\n\n" * 20
    )
    settings = Settings(docs_path=docs_dir, db_path=tmp_path / "chroma")
    build_index(settings)
    return settings

def test_search_returns_results(indexed_settings):
    results = search("how to deploy", indexed_settings)
    assert len(results) >= 1

def test_search_result_has_citation(indexed_settings):
    results = search("kubectl deployment", indexed_settings)
    assert results[0]["citation"].startswith("[source:")
    assert "deploy.md" in results[0]["citation"]
    assert ":L" in results[0]["citation"]

def test_search_citation_format(indexed_settings):
    results = search("deploy", indexed_settings)
    citation = results[0]["citation"]
    # Must match [source: filename.md:L42-L58]
    import re
    assert re.match(r"\[source: .+\.md:L\d+-L\d+\]", citation)

def test_list_sources_returns_filenames(indexed_settings):
    sources = list_sources(indexed_settings)
    assert "deploy.md" in sources
    assert "onboarding.md" in sources
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_searcher.py -v
```
Expected: `ImportError` for `src.searcher`

- [ ] **Step 3: Implement src/searcher.py**

```python
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from src.config import Settings


def _get_collection(settings: Settings):
    client = chromadb.PersistentClient(path=str(settings.db_path))
    ef = SentenceTransformerEmbeddingFunction(model_name=settings.model_name)
    return client.get_collection("kb", embedding_function=ef)


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
    """Return unique filenames currently in the index."""
    col = _get_collection(settings)
    all_meta = col.get(include=["metadatas"])["metadatas"]
    return sorted({m["source"] for m in all_meta})
```

- [ ] **Step 4: Run tests — all must pass**

```bash
pytest tests/test_searcher.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/searcher.py tests/test_searcher.py
git commit -m "feat: semantic search with L-range citations"
```

---

### Task 4: MCP server (the main event)

**Files:**
- Create: `src/server.py`

**Interfaces:**
- Consumes: `search(query, settings)` and `list_sources(settings)` from `src/searcher.py`
- Produces: MCP server exposing two tools over stdio:
  - `search_docs(query: str)` → formatted string of results with citations
  - `list_docs()` → formatted list of indexed filenames

- [ ] **Step 1: Implement src/server.py**

```python
import os
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from src.config import Settings
from src.searcher import search, list_sources

DOCS_PATH = Path(os.environ.get("KB_DOCS_PATH", "./docs"))
DB_PATH = Path(os.environ.get("KB_DB_PATH", str(Path.home() / ".mcp-kb" / "chroma")))

settings = Settings(docs_path=DOCS_PATH, db_path=DB_PATH)
server = Server("mcp-knowledge-base")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_docs",
            description="Search the indexed markdown knowledge base. Returns relevant chunks with source citations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language question or keyword search"}
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="list_docs",
            description="List all markdown files currently indexed in the knowledge base.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "search_docs":
        query = arguments["query"]
        results = search(query, settings)
        if not results:
            return [types.TextContent(type="text", text="No results found.")]
        lines = []
        for r in results:
            lines.append(f"{r['citation']}\n{r['text']}\n")
        return [types.TextContent(type="text", text="\n---\n".join(lines))]

    if name == "list_docs":
        sources = list_sources(settings)
        if not sources:
            return [types.TextContent(type="text", text="No documents indexed. Run: python index.py --docs <path>")]
        text = "Indexed documents:\n" + "\n".join(f"- {s}" for s in sources)
        return [types.TextContent(type="text", text=text)]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

- [ ] **Step 2: Manual smoke test (no index needed yet)**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python src/server.py
```
Expected: JSON response listing `search_docs` and `list_docs`

- [ ] **Step 3: Commit**

```bash
git add src/server.py
git commit -m "feat: MCP server with search_docs and list_docs tools"
```

---

### Task 5: CLI indexer entry point

**Files:**
- Create: `index.py`
- Create: `example-docs/deployment-runbook.md`
- Create: `example-docs/api-reference.md`

**Interfaces:**
- Consumes: `build_index` from `src/indexer.py`, `Settings` from `src/config.py`
- Produces: `python index.py --docs <path>` CLI command

- [ ] **Step 1: Add two more example docs**

`example-docs/deployment-runbook.md`:
```markdown
# Deployment Runbook

## Pre-deploy checklist

- [ ] All tests passing on CI
- [ ] Staging deploy verified by QA
- [ ] Feature flags configured in LaunchDarkly

## Deploy steps

1. Merge PR to main
2. GitHub Actions triggers deploy pipeline
3. Monitor Datadog dashboard for error rate spike (threshold: >1% over 5 min)
4. If error rate spikes, run rollback: `./scripts/rollback.sh <previous-sha>`

## Rollback

```bash
./scripts/rollback.sh abc1234
```

This redeploys the previous image tag. Takes ~3 minutes. Notify #incidents in Slack.
```

`example-docs/api-reference.md`:
```markdown
# API Reference

## Authentication

All requests require a Bearer token in the Authorization header.

```
Authorization: Bearer <token>
```

Tokens expire after 24 hours. Refresh via `POST /auth/refresh`.

## Endpoints

### GET /health

Returns 200 if the service is healthy. No auth required.

### POST /documents

Upload a document for processing.

**Body:** `multipart/form-data` with field `file` (PDF or DOCX, max 50MB)

**Response:** `{"id": "doc_abc123", "status": "processing"}`
```

- [ ] **Step 2: Create index.py**

```python
#!/usr/bin/env python3
"""CLI to index a folder of markdown docs into the local ChromaDB store."""
import typer
from pathlib import Path
from src.config import Settings
from src.indexer import build_index

app = typer.Typer()

@app.command()
def main(
    docs: Path = typer.Option(..., "--docs", "-d", help="Path to folder of .md files"),
    db: Path = typer.Option(
        Path.home() / ".mcp-kb" / "chroma",
        "--db",
        help="ChromaDB storage path",
    ),
):
    """Index markdown docs for the MCP knowledge base server."""
    if not docs.exists():
        typer.echo(f"Error: docs path does not exist: {docs}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Indexing docs from: {docs}")
    settings = Settings(docs_path=docs, db_path=db)
    count = build_index(settings)
    typer.echo(f"Done. Indexed {count} chunks from {docs}")
    typer.echo(f"Start server: KB_DOCS_PATH={docs} KB_DB_PATH={db} python src/server.py")

if __name__ == "__main__":
    app()
```

- [ ] **Step 3: End-to-end test — index then search**

```bash
python index.py --docs ./example-docs
```
Expected output: `Done. Indexed N chunks from ./example-docs`

```bash
KB_DOCS_PATH=./example-docs python -c "
from src.config import Settings
from pathlib import Path
from src.searcher import search, list_sources
s = Settings(docs_path=Path('./example-docs'))
print(list_sources(s))
print(search('how to rollback a deployment', s)[0]['citation'])
"
```
Expected: filenames listed, citation like `[source: deployment-runbook.md:L18-L24]`

- [ ] **Step 4: Commit**

```bash
git add index.py example-docs/
git commit -m "feat: CLI indexer and example docs"
```

---

### Task 6: README + Claude Desktop config

**Files:**
- Create: `README.md`
- Create: `claude_desktop_config.example.json`

- [ ] **Step 1: Create claude_desktop_config.example.json**

```json
{
  "mcpServers": {
    "knowledge-base": {
      "command": "python",
      "args": ["/absolute/path/to/mcp-knowledge-base/src/server.py"],
      "env": {
        "KB_DOCS_PATH": "/absolute/path/to/your/docs",
        "KB_DB_PATH": "/Users/yourname/.mcp-kb/chroma"
      }
    }
  }
}
```

- [ ] **Step 2: Create README.md**

```markdown
# MCP Knowledge Base

MCP server that turns any folder of markdown docs into a searchable knowledge base for Claude Desktop and Cursor.  
Deploy in 5 minutes. Works with any MCP client.

## How it works

1. You run `index.py` once — it chunks your `.md` files and stores vectors locally (ChromaDB).
2. The MCP server loads that index on startup.
3. Claude gets two tools: `search_docs` (semantic search with cited answers) and `list_docs` (see what's indexed).
4. Zero external accounts. Everything runs on your machine.

## Quickstart

```bash
git clone https://github.com/yourusername/mcp-knowledge-base
cd mcp-knowledge-base
pip install -e .

# Index your docs (run once, re-run when docs change)
python index.py --docs ./example-docs

# Test the server
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python src/server.py
```

## Connect to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "knowledge-base": {
      "command": "python",
      "args": ["/absolute/path/to/mcp-knowledge-base/src/server.py"],
      "env": {
        "KB_DOCS_PATH": "/path/to/your/docs",
        "KB_DB_PATH": "/Users/yourname/.mcp-kb/chroma"
      }
    }
  }
}
```

Restart Claude Desktop. Ask: *"What docs do you have access to?"* or *"How do I roll back a deployment?"*

## Example output

```
[source: deployment-runbook.md:L18-L24]
If error rate spikes, run rollback: ./scripts/rollback.sh <previous-sha>
This redeploys the previous image tag. Takes ~3 minutes.
```

## Tools exposed

| Tool | Description |
|------|-------------|
| `search_docs(query)` | Semantic search, returns top-5 chunks with L-range citations |
| `list_docs()` | Lists all indexed markdown filenames |

## Stack

- [MCP SDK](https://github.com/anthropics/mcp) — official Anthropic MCP server framework
- [ChromaDB](https://www.trychroma.com/) — local vector store, no account needed
- [sentence-transformers](https://www.sbert.net/) — `all-MiniLM-L6-v2`, runs fully offline
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all tests PASSED

- [ ] **Step 4: Final commit**

```bash
git add README.md claude_desktop_config.example.json
git commit -m "docs: README and Claude Desktop config example"
```

- [ ] **Step 5: Push to GitHub**

```bash
git remote add origin https://github.com/yourusername/mcp-knowledge-base.git
git push -u origin main
```
