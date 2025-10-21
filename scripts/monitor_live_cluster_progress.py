#!/usr/bin/env python3
"""
Real-time progress monitor for live-cluster evaluation.

Tracks namespace creation patterns to estimate progress and completion time.

Usage:
    python scripts/monitor_live_cluster_progress.py --pid 59028
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor live-cluster evaluation progress."
    )
    parser.add_argument(
        "--pid",
        type=int,
        required=True,
        help="Process ID of the live-cluster evaluation.",
    )
    parser.add_argument(
        "--total",
        type=int,
        default=200,
        help="Total number of manifests being processed.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Polling interval in seconds.",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="live-eval",
        help="Namespace prefix to track (exclude -validate-).",
    )
    return parser.parse_args()


def check_process_running(pid: int) -> bool:
    """Check if a process is running."""
    try:
        subprocess.run(
            ["ps", "-p", str(pid)],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_process_elapsed(pid: int) -> Optional[str]:
    """Get elapsed time for a process."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "etime="],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_namespace_info(prefix: str) -> Tuple[int, int, Dict[str, str]]:
    """
    Get namespace information.
    
    Returns:
        (active_count, terminating_count, namespace_ages)
    """
    try:
        result = subprocess.run(
            ["kubectl", "get", "namespaces", "-o", "custom-columns=NAME:.metadata.name,STATUS:.status.phase,AGE:.metadata.creationTimestamp"],
            capture_output=True,
            text=True,
            check=True,
        )
        
        namespaces = {}
        active = 0
        terminating = 0
        
        for line in result.stdout.strip().split("\n")[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                status = parts[1] if len(parts) > 1 else "Unknown"
                
                # Filter for our prefix but exclude validation namespaces
                if prefix in name and "validate" not in name:
                    namespaces[name] = status
                    if status == "Active":
                        active += 1
                    elif status == "Terminating":
                        terminating += 1
        
        return active, terminating, namespaces
    except subprocess.CalledProcessError:
        return 0, 0, {}


def parse_elapsed_time(elapsed_str: str) -> int:
    """Convert elapsed time string to seconds."""
    parts = elapsed_str.strip().split(":")
    if len(parts) == 3:
        # HH:MM:SS
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:
        # MM:SS
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    elif len(parts) == 1:
        # SS
        return int(parts[0])
    return 0


def format_duration(seconds: int) -> str:
    """Format seconds into HH:MM:SS."""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    elif minutes > 0:
        return f"{minutes}m {secs:02d}s"
    else:
        return f"{secs}s"


class ProgressTracker:
    """Track progress over time and estimate completion."""
    
    def __init__(self, total: int, window_size: int = 10):
        self.total = total
        self.window_size = window_size
        self.history: deque = deque(maxlen=window_size)
        self.start_time = time.time()
        self.max_seen = 0
    
    def update(self, namespace_count: int, elapsed_seconds: int) -> None:
        """Update progress with new observation."""
        # Track maximum namespaces seen (cumulative processed)
        if namespace_count > self.max_seen:
            self.max_seen = namespace_count
        
        self.history.append({
            "timestamp": time.time(),
            "elapsed": elapsed_seconds,
            "count": namespace_count,
            "max_seen": self.max_seen,
        })
    
    def estimate_progress(self) -> Tuple[int, float, Optional[int]]:
        """
        Estimate current progress.
        
        Returns:
            (estimated_processed, rate_per_minute, eta_seconds)
        """
        if len(self.history) < 2:
            return self.max_seen, 0.0, None
        
        # Use cumulative max as estimate (namespaces are cleaned up async)
        estimated_processed = self.max_seen
        
        # Calculate rate from recent history
        recent = list(self.history)[-5:]  # Last 5 observations
        if len(recent) >= 2:
            time_delta = recent[-1]["timestamp"] - recent[0]["timestamp"]
            count_delta = recent[-1]["max_seen"] - recent[0]["max_seen"]
            
            if time_delta > 0:
                rate_per_sec = count_delta / time_delta
                rate_per_min = rate_per_sec * 60
            else:
                rate_per_min = 0.0
        else:
            rate_per_min = 0.0
        
        # Estimate ETA
        if rate_per_min > 0:
            remaining = self.total - estimated_processed
            eta_seconds = int((remaining / rate_per_min) * 60)
        else:
            eta_seconds = None
        
        return estimated_processed, rate_per_min, eta_seconds
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        if not self.history:
            return {}
        
        latest = self.history[-1]
        estimated, rate, eta = self.estimate_progress()
        
        return {
            "elapsed": latest["elapsed"],
            "estimated_processed": estimated,
            "total": self.total,
            "percentage": (estimated / self.total * 100) if self.total > 0 else 0,
            "rate_per_minute": rate,
            "eta_seconds": eta,
            "current_namespaces": latest["count"],
        }


def print_progress_bar(percentage: float, width: int = 40) -> str:
    """Generate a text progress bar."""
    filled = int(width * percentage / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {percentage:.1f}%"


def main() -> None:
    args = parse_args()
    
    # Check if process exists
    if not check_process_running(args.pid):
        print(f"Error: Process {args.pid} is not running")
        sys.exit(1)
    
    print(f"{'='*80}")
    print(f"Live-Cluster Evaluation Progress Monitor")
    print(f"{'='*80}")
    print(f"Process ID: {args.pid}")
    print(f"Total manifests: {args.total}")
    print(f"Polling interval: {args.interval}s")
    print(f"Namespace prefix: {args.prefix}")
    print(f"{'='*80}")
    print()
    
    tracker = ProgressTracker(total=args.total)
    iteration = 0
    
    try:
        while True:
            iteration += 1
            
            # Check if process is still running
            if not check_process_running(args.pid):
                print("\n" + "="*80)
                print("Process completed!")
                print("="*80)
                
                # Check if results file exists
                results_path = Path("data/live_cluster/results.json")
                if results_path.exists():
                    import json
                    results = json.loads(results_path.read_text())
                    print(f"Results file created: {len(results)} manifests processed")
                else:
                    print("Results file not found yet (may still be writing)")
                
                break
            
            # Get elapsed time
            elapsed_str = get_process_elapsed(args.pid)
            elapsed_seconds = parse_elapsed_time(elapsed_str) if elapsed_str else 0
            
            # Get namespace counts
            active, terminating, namespaces = get_namespace_info(args.prefix)
            total_ns = active + terminating
            
            # Update tracker
            tracker.update(total_ns, elapsed_seconds)
            stats = tracker.get_stats()
            
            # Clear previous lines (if not first iteration)
            if iteration > 1:
                print("\033[F" * 10)  # Move cursor up 10 lines
            
            # Display header
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{timestamp}] Iteration {iteration} | Elapsed: {format_duration(elapsed_seconds)}")
            print("-" * 80)
            
            # Progress bar
            print(f"\nProgress: {print_progress_bar(stats['percentage'])}")
            print(f"Estimated: {stats['estimated_processed']}/{args.total} manifests")
            
            # Rate and ETA
            if stats['rate_per_minute'] > 0:
                print(f"Rate: {stats['rate_per_minute']:.2f} manifests/min")
                if stats['eta_seconds']:
                    eta_str = format_duration(stats['eta_seconds'])
                    eta_time = datetime.now() + timedelta(seconds=stats['eta_seconds'])
                    print(f"ETA: {eta_str} (completion ~{eta_time.strftime('%H:%M:%S')})")
            else:
                print("Rate: Calculating...")
                print("ETA: Calculating...")
            
            # Namespace status
            print(f"\nNamespace status:")
            print(f"  Active: {active}")
            print(f"  Terminating: {terminating}")
            print(f"  Total tracked: {total_ns}")
            
            # Wait for next interval
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*80)
        print("Monitoring stopped (process still running in background)")
        print(f"Process PID: {args.pid}")
        print("="*80)


if __name__ == "__main__":
    main()



