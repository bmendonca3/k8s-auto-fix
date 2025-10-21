#!/usr/bin/env python3
"""
Finalize live-cluster evaluation by updating paper with actual results.

This script:
1. Waits for the live-cluster evaluation to complete
2. Reads the results from data/live_cluster/results.json and summary.csv
3. Updates paper/access.tex with the actual statistics
4. Recompiles the LaTeX document

Usage:
    python scripts/finalize_live_cluster_results.py [--wait]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize live-cluster evaluation results in paper."
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the evaluation process to complete.",
    )
    parser.add_argument(
        "--pid",
        type=int,
        help="PID of the live-cluster evaluation process to wait for.",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("data/live_cluster/results.json"),
        help="Path to results JSON file.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/live_cluster/summary.csv"),
        help="Path to summary CSV file.",
    )
    parser.add_argument(
        "--paper",
        type=Path,
        default=Path("paper/access.tex"),
        help="Path to LaTeX paper file.",
    )
    return parser.parse_args()


def wait_for_process(pid: int) -> None:
    """Wait for a process to complete."""
    print(f"Waiting for process {pid} to complete...")
    start_time = time.time()
    
    while True:
        try:
            # Check if process exists
            subprocess.run(
                ["ps", "-p", str(pid)],
                capture_output=True,
                check=True,
            )
            # Process still running
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            print(f"\rWaiting... {mins:02d}:{secs:02d} elapsed", end="", flush=True)
            time.sleep(10)
        except subprocess.CalledProcessError:
            # Process completed
            print(f"\nProcess {pid} completed after {elapsed} seconds")
            break


def read_results(results_path: Path, summary_path: Path) -> dict:
    """Read and analyze live-cluster results."""
    if not results_path.exists():
        raise FileNotFoundError(f"Results file {results_path} not found")
    
    if not summary_path.exists():
        raise FileNotFoundError(f"Summary file {summary_path} not found")
    
    # Read results
    results = json.loads(results_path.read_text())
    
    # Read summary
    with summary_path.open("r") as fh:
        lines = fh.readlines()
        if len(lines) < 2:
            raise ValueError("Summary file is incomplete")
        
        header = lines[0].strip().split(",")
        values = lines[1].strip().split(",")
        summary = dict(zip(header, values))
    
    # Calculate statistics
    total = len(results)
    dry_run_pass = sum(1 for r in results if r.get("dry_run_pass"))
    live_apply_pass = sum(1 for r in results if r.get("live_apply_pass"))
    failures = sum(1 for r in results if r.get("live_apply_pass") is False)
    rollbacks = sum(1 for r in results if r.get("rollback_triggered"))
    
    dry_run_rate = (dry_run_pass / total * 100) if total > 0 else 0
    live_apply_rate = (live_apply_pass / total * 100) if total > 0 else 0
    
    return {
        "total": total,
        "dry_run_pass": dry_run_pass,
        "dry_run_rate": dry_run_rate,
        "live_apply_pass": live_apply_pass,
        "live_apply_rate": live_apply_rate,
        "failures": failures,
        "rollbacks": rollbacks,
        "summary": summary,
    }


def update_paper(paper_path: Path, stats: dict) -> None:
    """Update the paper with live-cluster statistics."""
    if not paper_path.exists():
        raise FileNotFoundError(f"Paper file {paper_path} not found")
    
    content = paper_path.read_text()
    
    # Find and replace the live-cluster validation bullet point
    old_text = (
        r"    \item \textbf{Live-cluster validation:}\\ The staging harness "
        r"(\texttt{scripts/run\_live\_cluster\_eval.py}) replays a 13-manifest "
        r"subset on a Kind staging cluster with 100\% dry-run/live-apply success "
        r"(\texttt{data/manifests\_live\_subset/}, \texttt{data/live\_cluster/results.json}, "
        r"\texttt{data/live\_cluster/summary.csv})."
    )
    
    new_text = (
        f"    \\item \\textbf{{Live-cluster validation:}}\\\\ The staging harness "
        f"(\\texttt{{scripts/run\\_live\\_cluster\\_eval.py}}) replays a stratified "
        f"{stats['total']}-manifest sample on a Kind cluster "
        f"with {stats['dry_run_rate']:.1f}\\% dry-run success "
        f"({stats['dry_run_pass']}/{stats['total']} manifests) and "
        f"{stats['live_apply_rate']:.1f}\\% live-apply success "
        f"({stats['live_apply_pass']}/{stats['total']} manifests). "
        f"Rollback was triggered for {stats['rollbacks']} manifest(s) where dry-run "
        f"passed but live-apply failed "
        f"(\\texttt{{data/live\\_cluster/batch/}}, "
        f"\\texttt{{data/live\\_cluster/results.json}}, "
        f"\\texttt{{data/live\\_cluster/summary.csv}})."
    )
    
    if old_text in content:
        content = content.replace(old_text, new_text)
        paper_path.write_text(content)
        print(f"Updated {paper_path} with live-cluster results")
    else:
        print("Warning: Could not find the live-cluster validation bullet point")
        print("Manual update may be required")


def recompile_paper(paper_path: Path) -> None:
    """Recompile the LaTeX paper."""
    paper_dir = paper_path.parent
    paper_name = paper_path.stem
    
    print(f"Recompiling {paper_name}.tex...")
    
    for i in range(2):
        proc = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", f"{paper_name}.tex"],
            cwd=paper_dir,
            capture_output=True,
            text=True,
        )
        
        if proc.returncode != 0:
            print(f"Error compiling LaTeX (attempt {i+1}):")
            print(proc.stderr)
            sys.exit(1)
    
    pdf_path = paper_dir / f"{paper_name}.pdf"
    if pdf_path.exists():
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        print(f"Successfully compiled {pdf_path} ({size_mb:.1f} MB)")
    else:
        print("Warning: PDF file not found after compilation")


def main() -> None:
    args = parse_args()
    
    # Wait for process if requested
    if args.wait and args.pid:
        wait_for_process(args.pid)
    
    # Read results
    print(f"Reading results from {args.results} and {args.summary}...")
    stats = read_results(args.results, args.summary)
    
    print(f"\nLive-Cluster Evaluation Results:")
    print(f"  Total manifests: {stats['total']}")
    print(f"  Dry-run pass: {stats['dry_run_pass']} ({stats['dry_run_rate']:.1f}%)")
    print(f"  Live-apply pass: {stats['live_apply_pass']} ({stats['live_apply_rate']:.1f}%)")
    print(f"  Failures: {stats['failures']}")
    print(f"  Rollbacks: {stats['rollbacks']}")
    print()
    
    # Update paper
    update_paper(args.paper, stats)
    
    # Recompile
    recompile_paper(args.paper)
    
    print("\nFinalization complete!")


if __name__ == "__main__":
    main()



