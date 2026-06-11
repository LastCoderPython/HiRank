import argparse
import asyncio
import json
import math
import os
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


class SingleResult:
    def __init__(
        self,
        label: str,
        category: str,
        ttft_ms: float,
        total_ms: float,
        response_time_ms: Optional[float],
        error: Optional[str] = None,
    ):
        self.label = label
        self.category = category
        self.ttft_ms = ttft_ms
        self.total_ms = total_ms
        self.response_time_ms = response_time_ms
        self.error = error


class BenchmarkResult:
    def __init__(self, warmup: int, total: int):
        self.warmup = warmup
        self.total = total
        self.results: List[SingleResult] = []
        self.errors: List[SingleResult] = []

    def add(self, r: SingleResult) -> None:
        if r.error:
            self.errors.append(r)
        else:
            self.results.append(r)

    @property
    def success_count(self) -> int:
        return len(self.results)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def all_ttft(self) -> List[float]:
        return [r.ttft_ms for r in self.results]

    def all_total(self) -> List[float]:
        return [r.total_ms for r in self.results]

    def all_response_time(self) -> List[float]:
        vals = [r.response_time_ms for r in self.results if r.response_time_ms is not None]
        return vals

    def by_category(self) -> Dict[str, List[SingleResult]]:
        groups: Dict[str, List[SingleResult]] = defaultdict(list)
        for r in self.results:
            groups[r.category].append(r)
        return dict(groups)


def percentile(data: List[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (p / 100.0) * (len(s) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def compute_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"count": 0, "min": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "mean": 0.0, "stdev": 0.0}
    mean = statistics.mean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "count": len(values),
        "min": min(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values),
        "mean": round(mean, 2),
        "stdev": round(stdev, 2),
    }


def load_queries(path: str) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        print("ERROR: queries file is empty")
        sys.exit(1)
    return data


def generate_session_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def wait_time(min_wait: float, max_wait: float) -> float:
    return random.uniform(min_wait, max_wait)


class SSEParser:
    def __init__(self):
        self.first_data_event = False
        self.found_done = False

    def feed_line(self, line: str) -> None:
        stripped = line.strip()
        if stripped.startswith("data: "):
            if not self.first_data_event:
                self.first_data_event = True
            try:
                payload = json.loads(stripped[len("data: "):])
                if payload.get("type") == "done":
                    self.found_done = True
            except json.JSONDecodeError:
                pass

    def is_complete(self) -> bool:
        return self.found_done


async def measure_single(
    client: httpx.AsyncClient,
    url: str,
    query: Dict[str, str],
    session_id: str,
    timeout: float,
) -> SingleResult:
    label = query.get("label", "unknown")
    category = query.get("category", "unknown")
    message = query["message"]

    payload = {
        "message": message,
        "session_id": session_id,
    }

    try:
        start = time.monotonic()
        async with client.stream(
            "POST",
            url,
            json=payload,
            timeout=httpx.Timeout(timeout),
        ) as response:
            first_byte = time.monotonic()
            ttft_ms = (first_byte - start) * 1000

            parser = SSEParser()
            async for raw_line in response.aiter_lines():
                parser.feed_line(raw_line)
                if parser.is_complete():
                    break

            end = time.monotonic()
            total_ms = (end - start) * 1000

            response_time_header = response.headers.get("x-response-time-ms")
            response_time_ms = float(response_time_header) if response_time_header else None

            if response.status_code != 200:
                return SingleResult(
                    label=label,
                    category=category,
                    ttft_ms=ttft_ms,
                    total_ms=0,
                    response_time_ms=response_time_ms,
                    error=f"HTTP {response.status_code}",
                )

            if not parser.first_data_event:
                return SingleResult(
                    label=label,
                    category=category,
                    ttft_ms=ttft_ms,
                    total_ms=total_ms,
                    response_time_ms=response_time_ms,
                    error="No SSE data events received",
                )

            return SingleResult(
                label=label,
                category=category,
                ttft_ms=ttft_ms,
                total_ms=total_ms,
                response_time_ms=response_time_ms,
            )

    except httpx.TimeoutException:
        return SingleResult(
            label=label,
            category=category,
            ttft_ms=0,
            total_ms=0,
            response_time_ms=None,
            error="Timeout",
        )
    except Exception as e:
        return SingleResult(
            label=label,
            category=category,
            ttft_ms=0,
            total_ms=0,
            response_time_ms=None,
            error=str(e),
        )


async def run_benchmark(
    url: str,
    queries: List[Dict[str, str]],
    warmup: int,
    total: int,
    concurrency: int,
    min_wait: float,
    max_wait: float,
    session_prefix: str,
    timeout: float,
) -> BenchmarkResult:
    result = BenchmarkResult(warmup=warmup, total=total)
    sem = asyncio.Semaphore(concurrency)

    async def worker(query: Dict[str, str], sid: str) -> SingleResult:
        async with sem:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                return await measure_single(client, url, query, sid, timeout)

    print(f"Warmup: sending {warmup} request(s)...")
    for i in range(warmup):
        q = random.choice(queries)
        sid = generate_session_id(f"{session_prefix}-warmup")
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            r = await measure_single(client, url, q, sid, timeout)
        print(f"  warmup {i + 1}/{warmup}: {r.label} -> {'OK' if not r.error else r.error}")
        await asyncio.sleep(wait_time(min_wait, max_wait))

    print(f"Benchmark: sending {total} request(s) with concurrency={concurrency}...")
    done_count = 0
    i = 0
    while i < total:
        batch_size = min(concurrency, total - i)
        batch = []
        for j in range(batch_size):
            q = queries[(i + j) % len(queries)]
            sid = generate_session_id(f"{session_prefix}-bench")
            batch.append(worker(q, sid))

        for coro in asyncio.as_completed(batch):
            r = await coro
            result.add(r)
            done_count += 1
            marker = "OK" if not r.error else "ERR"
            print(f"  [{done_count}/{total}] {r.label:20s} TTFT={r.ttft_ms:>8.1f}ms  Total={r.total_ms:>8.1f}ms  [{marker}]")

        i += batch_size
        if i < total:
            await asyncio.sleep(wait_time(min_wait, max_wait))

    return result


def fmt_ms(ms: float) -> str:
    return f"{ms:>8,.0f}"


def _hr(char: str = "-", width: int = 60) -> str:
    return char * width


def print_table(result: BenchmarkResult) -> None:
    print()
    print(f"  Latency Benchmark Report")
    print(f"  {_hr('=')}")
    print(f"  Total requests: {result.total:>6}   Success: {result.success_count:>6}   Errors: {result.error_count:>6}   Warmup: {result.warmup:>6}")
    print(f"  {_hr('-')}")

    ttft_stats = compute_stats(result.all_ttft())
    total_stats = compute_stats(result.all_total())
    response_stats = compute_stats(result.all_response_time())

    header = f"  {'Metric':<25s} {'P50':>8s} {'P95':>8s} {'P99':>8s} {'Mean':>8s} {'Max':>8s} {'Stdev':>8s}"
    print(header)
    print(f"  {_hr('-', 73)}")
    print(f"  {'TTFT (ms)':<25s} {fmt_ms(ttft_stats['p50'])} {fmt_ms(ttft_stats['p95'])} {fmt_ms(ttft_stats['p99'])} {fmt_ms(ttft_stats['mean'])} {fmt_ms(ttft_stats['max'])} {fmt_ms(ttft_stats['stdev'])}")
    print(f"  {'Total (ms)':<25s} {fmt_ms(total_stats['p50'])} {fmt_ms(total_stats['p95'])} {fmt_ms(total_stats['p99'])} {fmt_ms(total_stats['mean'])} {fmt_ms(total_stats['max'])} {fmt_ms(total_stats['stdev'])}")
    if response_stats["count"] > 0:
        print(f"  {'x-response-time (ms)':<25s} {fmt_ms(response_stats['p50'])} {fmt_ms(response_stats['p95'])} {fmt_ms(response_stats['p99'])} {fmt_ms(response_stats['mean'])} {fmt_ms(response_stats['max'])} {fmt_ms(response_stats['stdev'])}")

    print(f"  {_hr('-')}")
    print(f"  By Query Category")
    print(f"  {_hr('-', 60)}")
    for cat, items in result.by_category().items():
        cat_ttft = compute_stats([r.ttft_ms for r in items])
        cat_total = compute_stats([r.total_ms for r in items])
        print(f"  {cat:<15s} (n={len(items):>3})  TTFT p50={cat_ttft['p50']:>7,.0f}ms  Total p50={cat_total['p50']:>7,.0f}ms")

    if result.errors:
        print(f"  {_hr('-')}")
        print(f"  Errors ({result.error_count}):")
        for e in result.errors[:10]:
            print(f"    [{e.label}] {e.error}")
        if len(result.errors) > 10:
            print(f"    ... and {len(result.errors) - 10} more")


def print_histogram(result: BenchmarkResult, buckets: Optional[List[Tuple[float, str]]] = None) -> None:
    if buckets is None:
        buckets = [(0, "0 -  1s"), (1000, "1 -  2s"), (2000, "2 -  3s"), (3000, "3 -  5s"),
                   (5000, "5 - 10s"), (10000, "10 - 20s"), (20000, "20s+")]

    values = result.all_total()
    if not values:
        return

    print()
    print(f"  Latency Histogram (Total)")
    print(f"  {_hr('-', 48)}")

    max_count = 0
    counts = []
    for i, (low, label) in enumerate(buckets):
        high = buckets[i + 1][0] if i + 1 < len(buckets) else float("inf")
        count = sum(1 for v in values if low <= v < high)
        counts.append(count)
        max_count = max(max_count, count)

    bar_width = 28
    for (low, label), count in zip(buckets, counts):
        bar_len = int((count / max_count) * bar_width) if max_count > 0 else 0
        bar = "#" * bar_len + "." * (bar_width - bar_len)
        print(f"  {label}: [{bar}] {count:>4}")

    print()


def save_report(result: BenchmarkResult, path: str) -> None:
    ttft_stats = compute_stats(result.all_ttft())
    total_stats = compute_stats(result.all_total())
    response_stats = compute_stats(result.all_response_time())

    by_cat = {}
    for cat, items in result.by_category().items():
        by_cat[cat] = {
            "count": len(items),
            "ttft_ms": compute_stats([r.ttft_ms for r in items]),
            "total_ms": compute_stats([r.total_ms for r in items]),
        }

    raw = [
        {
            "label": r.label,
            "category": r.category,
            "ttft_ms": r.ttft_ms,
            "total_ms": r.total_ms,
            "response_time_ms": r.response_time_ms,
            "error": r.error,
        }
        for r in [*result.results, *result.errors]
    ]

    report = {
        "summary": {
            "total_requests": result.total,
            "success_count": result.success_count,
            "error_count": result.error_count,
            "warmup_count": result.warmup,
        },
        "latencies_ms": {
            "ttft": ttft_stats,
            "total": total_stats,
            "x_response_time": response_stats,
        },
        "by_category": by_cat,
        "raw_results": raw,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved to {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RankRoute Latency Benchmark Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/benchmark_latency.py
  python scripts/benchmark_latency.py --url http://localhost:80 --total 100 --concurrency 5
  python scripts/benchmark_latency.py --warmup 10 --min-wait 1 --max-wait 3
        """,
    )
    parser.add_argument("--url", default=os.getenv("BENCHMARK_URL", "http://localhost:9000/api/chat"),
                        help="API endpoint URL (default: http://localhost:9000/api/chat)")
    parser.add_argument("--queries", default=str(Path(__file__).parent / "benchmark_queries.json"),
                        help="Path to queries JSON file")
    parser.add_argument("--warmup", type=int, default=5, help="Number of warmup requests (default: 5)")
    parser.add_argument("--total", type=int, default=50, help="Total benchmark requests (default: 50)")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent requests (default: 1)")
    parser.add_argument("--min-wait", type=float, default=6.0,
                        help="Min wait between requests in seconds (default: 6.0, for 10 req/min)")
    parser.add_argument("--max-wait", type=float, default=8.0, help="Max wait between requests (default: 8.0)")
    parser.add_argument("--session-prefix", default="bench", help="Session ID prefix (default: bench)")
    parser.add_argument("--timeout", type=float, default=120.0, help="Request timeout in seconds (default: 120)")
    parser.add_argument("--output", default="latency_report.json", help="Output JSON file path")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    queries = load_queries(args.queries)

    print(f"  Target URL:       {args.url}")
    print(f"  Queries file:     {args.queries} ({len(queries)} queries)")
    print(f"  Warmup:           {args.warmup}")
    print(f"  Total requests:   {args.total}")
    print(f"  Concurrency:      {args.concurrency}")
    print(f"  Wait range:       {args.min_wait}-{args.max_wait}s")
    print(f"  Session prefix:   {args.session_prefix}")
    print(f"  Request timeout:  {args.timeout}s")
    print()

    result = await run_benchmark(
        url=args.url,
        queries=queries,
        warmup=args.warmup,
        total=args.total,
        concurrency=args.concurrency,
        min_wait=args.min_wait,
        max_wait=args.max_wait,
        session_prefix=args.session_prefix,
        timeout=args.timeout,
    )

    print_table(result)
    print_histogram(result)
    save_report(result, args.output)


if __name__ == "__main__":
    asyncio.run(main())
