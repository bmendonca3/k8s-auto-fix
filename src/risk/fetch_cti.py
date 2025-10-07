from __future__ import annotations

import gzip
import io
from pathlib import Path
from typing import Optional

import httpx
import typer


DEFAULT_EPSS_CANDIDATES = [
    "https://epss.cyentia.com/epss_scores-current.csv.gz",
    "https://epss.cyentia.com/epss_scores-current.csv",
]

DEFAULT_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


def fetch(
    out_dir: Path = typer.Option(Path("data"), exists=False, file_okay=False, dir_okay=True),
    epss_url: Optional[str] = typer.Option(None, help="Override EPSS CSV(.gz) URL"),
    kev_url: Optional[str] = typer.Option(None, help="Override CISA KEV JSON URL"),
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    epss_path = out_dir / "epss.csv"
    kev_path = out_dir / "kev.json"

    # Fetch EPSS
    urls = [epss_url] if epss_url else DEFAULT_EPSS_CANDIDATES
    for url in urls:
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()
                content = r.content
                # If gzipped
                if url.endswith(".gz"):
                    with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                        decoded = gz.read()
                    epss_path.write_bytes(decoded)
                else:
                    epss_path.write_bytes(content)
            typer.echo(f"Fetched EPSS -> {epss_path}")
            break
        except Exception:
            continue
    else:
        typer.echo("Warning: failed to fetch EPSS from known URLs; skipping EPSS")

    # Fetch KEV
    kev_source = kev_url or DEFAULT_KEV_URL
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(kev_source)
            r.raise_for_status()
            kev_path.write_bytes(r.content)
        typer.echo(f"Fetched KEV -> {kev_path}")
    except Exception:
        typer.echo("Warning: failed to fetch KEV; skipping KEV")


if __name__ == "__main__":  # pragma: no cover
    typer.run(fetch)


