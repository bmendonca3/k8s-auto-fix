#!/usr/bin/env python3
"""Batch OCR extraction for PDFs in the verification directory."""

import argparse
import json
from pathlib import Path
import time
from typing import Iterable, List

import requests
from requests import RequestException


API_URL = "https://api.alphaxiv.org/models/v1/deepseek/deepseek-ocr/inference"


def iter_pdfs(directory: Path) -> Iterable[Path]:
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() == ".pdf":
            yield path


def resolve_targets(paths: List[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file():
            if path.suffix.lower() == ".pdf":
                yield path
            continue
        if path.is_dir():
            yield from iter_pdfs(path)


def run_ocr(pdf_path: Path, attempts: int = 4, backoff: float = 5.0) -> str:
    for attempt in range(1, attempts + 1):
        try:
            with pdf_path.open("rb") as handle:
                response = requests.post(API_URL, files={"file": handle}, timeout=60)
        except RequestException:
            if attempt == attempts:
                raise
            time.sleep(backoff * attempt)
            continue
        if response.status_code >= 500:
            if attempt == attempts:
                response.raise_for_status()
            time.sleep(backoff * attempt)
            continue
        response.raise_for_status()
        payload = response.json()
        try:
            return payload["data"]["ocr_text"]
        except KeyError as exc:
            raise ValueError(f"Unexpected response schema for {pdf_path}") from exc
    raise RuntimeError(f"Failed to OCR {pdf_path} after {attempts} attempts")


def write_output(text: str, pdf_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / (pdf_path.stem + ".txt")
    target.write_text(text, encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        help="PDF file or directory containing PDF files (repeatable)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("verification/ocr"),
        help="Directory to write extracted OCR text files",
    )
    args = parser.parse_args()

    results = []
    input_paths = args.input if args.input else [Path("verification")]
    targets = list(resolve_targets(input_paths))
    if not targets:
        raise SystemExit("No PDF files found in the provided input paths.")
    for pdf in targets:
        print(f"OCR {pdf}...", flush=True)
        text = run_ocr(pdf)
        output_path = write_output(text, pdf, args.output)
        results.append({"pdf": str(pdf), "output": str(output_path)})

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
