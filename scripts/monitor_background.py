#!/usr/bin/env python3
"""
Background process monitoring with progress tracking and log tailing.

Usage:
    python scripts/monitor_background.py \\
        --name "Live Cluster Eval" \\
        --command "python scripts/run_live_cluster_eval.py ..." \\
        --logfile logs/live_cluster_eval.log \\
        --background
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor and manage background processes with live logging."
    )
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Human-readable name for this process.",
    )
    parser.add_argument(
        "--command",
        type=str,
        required=True,
        help="Command to execute (full shell command string).",
    )
    parser.add_argument(
        "--logfile",
        type=Path,
        required=True,
        help="Path to log file for stdout/stderr capture.",
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Run command in background and monitor it.",
    )
    parser.add_argument(
        "--tail",
        action="store_true",
        help="Tail an existing logfile (don't start a new process).",
    )
    parser.add_argument(
        "--pidfile",
        type=Path,
        help="Path to PID file (auto-generated if not provided).",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=20,
        help="Number of lines to show when tailing.",
    )
    parser.add_argument(
        "--update-interval",
        type=float,
        default=2.0,
        help="Seconds between progress updates.",
    )
    return parser.parse_args()


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    td = timedelta(seconds=int(seconds))
    parts = []
    if td.days > 0:
        parts.append(f"{td.days}d")
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def tail_file(path: Path, lines: int = 20) -> None:
    """Display last N lines of a file."""
    if not path.exists():
        print(f"[!] Log file {path} does not exist yet.")
        return
    
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            all_lines = fh.readlines()
            tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            for line in tail_lines:
                print(line.rstrip())
    except Exception as e:
        print(f"[!] Error tailing {path}: {e}")


def run_background(
    name: str,
    command: str,
    logfile: Path,
    pidfile: Optional[Path],
    update_interval: float,
) -> int:
    """Run command in background and monitor progress."""
    # Ensure log directory exists
    logfile.parent.mkdir(parents=True, exist_ok=True)
    
    # Auto-generate pidfile if not provided
    if pidfile is None:
        pidfile = logfile.parent / f"{logfile.stem}.pid"
    
    print(f"[*] Starting: {name}")
    print(f"[*] Command: {command}")
    print(f"[*] Log file: {logfile}")
    print(f"[*] PID file: {pidfile}")
    print()
    
    # Start process
    start_time = time.time()
    with logfile.open("w", encoding="utf-8") as log_fh:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid if sys.platform != "win32" else None,
        )
    
    # Write PID
    pidfile.write_text(str(proc.pid))
    
    print(f"[✓] Process started (PID: {proc.pid})")
    print(f"[*] Monitoring... (Ctrl+C to stop monitoring, process continues)")
    print()
    
    try:
        last_size = 0
        while proc.poll() is None:
            # Show elapsed time
            elapsed = time.time() - start_time
            print(f"\r[⏱️ ] Elapsed: {format_duration(elapsed)} | Status: Running", end="", flush=True)
            
            # Check if log file grew
            if logfile.exists():
                current_size = logfile.stat().st_size
                if current_size > last_size:
                    print()  # New line before showing new output
                    
                    # Read new content
                    with logfile.open("r", encoding="utf-8", errors="ignore") as fh:
                        fh.seek(last_size)
                        new_content = fh.read()
                        if new_content:
                            for line in new_content.rstrip().split("\n"):
                                print(f"  {line}")
                    
                    last_size = current_size
            
            time.sleep(update_interval)
        
        # Process finished
        elapsed = time.time() - start_time
        exit_code = proc.returncode
        
        print()
        print()
        print(f"[{'✓' if exit_code == 0 else '✗'}] Process completed")
        print(f"[*] Exit code: {exit_code}")
        print(f"[*] Duration: {format_duration(elapsed)}")
        print()
        
        # Show final log tail
        print(f"[*] Last {20} lines of output:")
        tail_file(logfile, lines=20)
        
        # Clean up PID file
        if pidfile.exists():
            pidfile.unlink()
        
        return exit_code
    
    except KeyboardInterrupt:
        print()
        print()
        print(f"[!] Monitoring interrupted (process {proc.pid} still running)")
        print(f"[*] To check status: ps -p {proc.pid}")
        print(f"[*] To tail logs: tail -f {logfile}")
        print(f"[*] To kill: kill {proc.pid}")
        return 0


def monitor_existing(logfile: Path, tail_lines: int) -> None:
    """Monitor an existing log file."""
    if not logfile.exists():
        print(f"[!] Log file {logfile} does not exist.")
        sys.exit(1)
    
    print(f"[*] Tailing {logfile} (Ctrl+C to exit)")
    print()
    
    # Show initial tail
    tail_file(logfile, lines=tail_lines)
    print()
    print("[*] Watching for updates...")
    
    try:
        # Follow the file
        with logfile.open("r", encoding="utf-8", errors="ignore") as fh:
            # Seek to end
            fh.seek(0, 2)
            
            while True:
                line = fh.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.5)
    except KeyboardInterrupt:
        print()
        print("[*] Stopped tailing.")


def main() -> None:
    args = parse_args()
    
    if args.tail:
        monitor_existing(args.logfile, args.tail_lines)
    elif args.background:
        exit_code = run_background(
            args.name,
            args.command,
            args.logfile,
            args.pidfile,
            args.update_interval,
        )
        sys.exit(exit_code)
    else:
        # Foreground execution with logging
        args.logfile.parent.mkdir(parents=True, exist_ok=True)
        with args.logfile.open("w", encoding="utf-8") as log_fh:
            proc = subprocess.run(
                args.command,
                shell=True,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
            )
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()



