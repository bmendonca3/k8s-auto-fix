from __future__ import annotations

from pathlib import Path
import json
import typer

from .queue import init_db, enqueue_from_verified, pick_next

app = typer.Typer(help="Persistent risk-aware patch queue")


@app.command()
def init(db: Path = typer.Option(Path("data/queue.db"), help="Queue database path.")) -> None:
    init_db(db)
    typer.echo(f"Initialized queue DB at {db}")


@app.command()
def enqueue(
    db: Path = typer.Option(Path("data/queue.db")),
    verified: Path = typer.Option(Path("data/verified.json")),
    detections: Path = typer.Option(Path("data/detections.json")),
    risk: Path = typer.Option(Path("data/risk.json")),
) -> None:
    count = enqueue_from_verified(db, verified, detections, risk)
    typer.echo(f"Enqueued {count} accepted patch(es)")


@app.command("next")
def next_item(
    db: Path = typer.Option(Path("data/queue.db")),
    alpha: float = typer.Option(1.0),
    kev_weight: float = typer.Option(1.0),
) -> None:
    item = pick_next(db, alpha=alpha, kev_weight=kev_weight)
    if not item:
        typer.echo("Queue empty")
        return
    typer.echo(json.dumps({
        "id": item.id,
        "policy_id": item.policy_id,
        "risk": item.risk,
        "p": item.probability,
        "Et": item.expected_time,
        "kev": item.kev,
    }, indent=2))


if __name__ == "__main__":  # pragma: no cover
    app()




