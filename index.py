#!/usr/bin/env python3
"""Index a folder of markdown docs into the local ChromaDB store."""
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
    count = build_index(Settings(docs_path=docs, db_path=db))
    typer.echo(f"Done. Indexed {count} chunks from {docs}")
    typer.echo(f"Start server: KB_DOCS_PATH={docs} KB_DB_PATH={db} python3 src/server.py")


if __name__ == "__main__":
    app()
