#!/usr/bin/env python3
"""
Retrieval eval: Recall@5 and MRR against a gold question set.
Usage: PYTHONPATH=. python3 eval.py --docs ./example-docs
"""
import typer
from pathlib import Path
from src.config import Settings
from src.indexer import build_index
from src.searcher import search

# Gold set: (question, expected_source_filename)
GOLD = [
    # onboarding.md
    ("how do I get AWS access on day one", "onboarding.md"),
    ("what tools do I install first", "onboarding.md"),
    ("where do I find the team wiki", "onboarding.md"),
    ("who do I talk to for a code review", "onboarding.md"),
    ("what is the onboarding checklist", "onboarding.md"),
    ("how do I set up my dev environment", "onboarding.md"),
    ("what Slack channels should I join", "onboarding.md"),
    # deployment-runbook.md
    ("how do I roll back a deployment", "deployment-runbook.md"),
    ("what is the rollback command", "deployment-runbook.md"),
    ("how long does a rollback take", "deployment-runbook.md"),
    ("what Datadog threshold triggers a rollback", "deployment-runbook.md"),
    ("which Slack channel for incidents", "deployment-runbook.md"),
    ("what is the deploy checklist", "deployment-runbook.md"),
    ("how do I deploy to production", "deployment-runbook.md"),
    # api-reference.md
    ("how do I authenticate with the API", "api-reference.md"),
    ("what is the bearer token format", "api-reference.md"),
    ("how long do tokens last", "api-reference.md"),
    ("how do I refresh my token", "api-reference.md"),
    ("what does the health endpoint return", "api-reference.md"),
    ("how do I upload a document", "api-reference.md"),
]

app = typer.Typer()


@app.command()
def main(
    docs: Path = typer.Option(..., "--docs", help="Docs folder (already indexed)"),
    db: Path = typer.Option(Path.home() / ".mcp-kb" / "chroma", "--db"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Re-index before eval"),
):
    settings = Settings(docs_path=docs, db_path=db)
    if rebuild:
        n = build_index(settings)
        typer.echo(f"Indexed {n} chunks")

    hits_at_5 = 0
    reciprocal_ranks = []

    for query, expected_source in GOLD:
        results = search(query, settings)
        sources = [r["source"] for r in results]
        if expected_source in sources:
            hits_at_5 += 1
            rank = sources.index(expected_source) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    n = len(GOLD)
    recall = hits_at_5 / n
    mrr = sum(reciprocal_ranks) / n

    typer.echo(f"\n{'Metric':<15} {'Value':>8}")
    typer.echo("-" * 25)
    typer.echo(f"{'Recall@5':<15} {recall:>8.3f}  ({hits_at_5}/{n})")
    typer.echo(f"{'MRR':<15} {mrr:>8.3f}")
    typer.echo(f"\nGold set: {n} questions across {len({s for _, s in GOLD})} docs")


if __name__ == "__main__":
    app()
