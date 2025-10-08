#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

API_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-4-fast-reasoning"


def build_payload(request_id: int) -> Dict[str, Any]:
    return {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": "You are a latency probe. Reply with the token OK."},
            {
                "role": "user",
                "content": f"Respond with the text 'OK'. This is request {request_id}.",
            },
        ],
        "temperature": 0,
        "max_tokens": 5,
    }


def make_request(
    request_id: int,
    timeout: float,
    headers: Dict[str, str],
) -> Tuple[int, float, Optional[int], Optional[int], Optional[str], Optional[str]]:
    start = time.perf_counter()
    status_code: Optional[int] = None
    usage_tokens: Optional[int] = None
    err: Optional[str] = None
    content: Optional[str] = None
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(API_URL, headers=headers, json=build_payload(request_id))
            status_code = response.status_code
            response.raise_for_status()
            data = response.json()
            usage = data.get("usage") or {}
            completion_tokens = usage.get("completion_tokens")
            prompt_tokens = usage.get("prompt_tokens")
            total_tokens = usage.get("total_tokens")
            usage_tokens = total_tokens or completion_tokens or prompt_tokens
            choices = data.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                content = message.get("content")
    except httpx.HTTPError as exc:
        err = str(exc)
    except Exception as exc:  # pragma: no cover - diagnostic
        err = str(exc)
    duration = time.perf_counter() - start
    return request_id, duration, status_code, usage_tokens, content, err


def run_probe(
    total_requests: int,
    concurrency: int,
    timeout: float,
) -> List[Dict[str, Any]]:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("Environment variable XAI_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    results: List[Dict[str, Any]] = []
    lock = threading.Lock()

    def submit_batch(batch_ids: List[int]) -> None:
        with ThreadPoolExecutor(max_workers=len(batch_ids)) as executor:
            future_map = {
                executor.submit(make_request, request_id, timeout, headers): request_id
                for request_id in batch_ids
            }
            for future in as_completed(future_map):
                request_id, duration, status_code, usage_tokens, content, err = future.result()
                with lock:
                    results.append(
                        {
                            "id": request_id,
                            "duration_sec": duration,
                            "status_code": status_code,
                            "usage_tokens": usage_tokens,
                            "content": content,
                            "error": err,
                        }
                    )

    next_id = 1
    while next_id <= total_requests:
        batch_end = min(total_requests, next_id + concurrency - 1)
        batch = list(range(next_id, batch_end + 1))
        submit_batch(batch)
        next_id += concurrency

    results.sort(key=lambda item: item["id"])
    return results


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    durations = [r["duration_sec"] for r in results]
    statuses = [r["status_code"] for r in results]
    errors = [r for r in results if r.get("error")]
    success = [r for r in results if r.get("error") is None and (r["status_code"] or 0) < 400]

    summary: Dict[str, Any] = {
        "total_requests": len(results),
        "success": len(success),
        "failures": len(errors),
        "status_counts": {code: statuses.count(code) for code in sorted(set(statuses))},
    }
    if durations:
        summary["latency_sec"] = {
            "min": min(durations),
            "median": statistics.median(durations),
            "p90": statistics.quantiles(durations, n=10)[8],
            "max": max(durations),
        }
    if success:
        tokens = [r["usage_tokens"] for r in success if r["usage_tokens"] is not None]
        if tokens:
            summary["token_usage"] = {
                "min": min(tokens),
                "median": statistics.median(tokens),
                "max": max(tokens),
            }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Grok API throughput/latency.")
    parser.add_argument("--requests", type=int, default=20, help="Total number of requests to send.")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent requests to issue.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-request timeout in seconds (matches proposer defaults).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the raw JSON results.",
    )
    args = parser.parse_args()

    if args.requests <= 0 or args.concurrency <= 0:
        raise SystemExit("requests and concurrency must be positive integers")

    start = time.perf_counter()
    results = run_probe(args.requests, args.concurrency, args.timeout)
    elapsed = time.perf_counter() - start

    summary = summarize(results)
    summary["wall_clock_sec"] = elapsed
    summary["concurrency"] = args.concurrency

    print(json.dumps(summary, indent=2))
    if args.output:
        payload = {
            "summary": summary,
            "results": results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
