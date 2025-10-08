from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd  # type: ignore
import requests
import yaml

DATASET_URL = (
    "https://huggingface.co/datasets/substratusai/the-stack-yaml-k8s/resolve/main/"
    "data/train-00000-of-00005-d8eb364753f1951d.parquet?download=true"
)


def download_parquet(url: str, token: Optional[str] = None) -> bytes:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with requests.get(url, headers=headers, stream=True, timeout=60) as response:
        response.raise_for_status()
        return response.content


def sample_manifests(
    limit: int,
    output_dir: Path,
    parquet_bytes: bytes,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(io.BytesIO(parquet_bytes))
    written = 0
    for _, row in df.iterrows():
        if written >= limit:
            break
        content = row.get("content")
        if not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue
        try:
            documents = list(yaml.safe_load_all(content))
        except yaml.YAMLError:
            continue
        valid_docs = [
            doc
            for doc in documents
            if isinstance(doc, dict) and doc.get("apiVersion") and doc.get("kind")
        ]
        if not valid_docs:
            continue
        output_path = output_dir / f"sample_{written:04d}.yaml"
        with output_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump_all(valid_docs, handle, sort_keys=False)
        written += 1
    return written


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sample Kubernetes manifests from the HuggingFace the-stack-yaml-k8s dataset."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Number of manifests to sample (default: 200).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/manifests/the_stack_sample"),
        help="Directory where sampled manifests will be written.",
    )
    parser.add_argument(
        "--use-temp-file",
        action="store_true",
        help="Persist the downloaded parquet to a temporary file for inspection.",
    )
    args = parser.parse_args(argv)

    token = os.getenv("HUGGINGFACE_TOKEN")
    try:
        parquet_bytes = download_parquet(DATASET_URL, token=token)
    except requests.HTTPError as exc:
        print(f"[the-stack] Failed to download dataset: {exc}", file=sys.stderr)
        return 1

    if args.use_temp_file:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".parquet")
        tmp.write(parquet_bytes)
        tmp.close()
        print(f"[the-stack] Saved parquet to {tmp.name} for inspection.")

    written = sample_manifests(args.limit, args.output_dir, parquet_bytes)
    print(f"[the-stack] Wrote {written} manifest(s) to {args.output_dir.resolve()}")
    if written < args.limit:
        print(
            f"[the-stack] Warning: only {written} manifests were produced (requested {args.limit}).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
