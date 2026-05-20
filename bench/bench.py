"""Latency / throughput benchmark for pricing-grpc-service.

Usage::

    python bench/bench.py --target localhost:50051 --concurrency 32 --duration 5
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import grpc

from pricing_grpc_service.generated import pricing_pb2, pricing_pb2_grpc


async def _worker(
    stub: pricing_pb2_grpc.PricingStub,
    deadline: float,
    latencies_ns: list[int],
    errors: list[grpc.StatusCode],
) -> int:
    request = pricing_pb2.QuoteRequest(symbol="BTC-USD")
    count = 0
    while time.perf_counter() < deadline:
        t0 = time.perf_counter_ns()
        try:
            await stub.GetQuote(request)
        except grpc.RpcError as exc:
            errors.append(exc.code())
            continue
        latencies_ns.append(time.perf_counter_ns() - t0)
        count += 1
    return count


def _percentile(sorted_values: list[int], pct: float) -> float:
    if not sorted_values:
        return float("nan")
    k = max(0, min(len(sorted_values) - 1, round((pct / 100) * (len(sorted_values) - 1))))
    return sorted_values[k]


async def run(target: str, concurrency: int, duration_s: float, warmup_s: float) -> None:
    async with grpc.aio.insecure_channel(target) as channel:
        stub = pricing_pb2_grpc.PricingStub(channel)

        # Warmup so we don't pay channel/handler init cost in the measured window.
        warmup_deadline = time.perf_counter() + warmup_s
        await asyncio.gather(
            *(_worker(stub, warmup_deadline, [], []) for _ in range(concurrency))
        )

        latencies_ns: list[int] = []
        errors: list[grpc.StatusCode] = []
        deadline = time.perf_counter() + duration_s
        t0 = time.perf_counter()
        await asyncio.gather(
            *(_worker(stub, deadline, latencies_ns, errors) for _ in range(concurrency))
        )
        elapsed = time.perf_counter() - t0

    total = len(latencies_ns)
    err_count = len(errors)
    if total == 0:
        print(f"no successful RPCs (errors={err_count})")
        return

    latencies_ns.sort()
    rps = total / elapsed
    p50 = _percentile(latencies_ns, 50) / 1e6
    p95 = _percentile(latencies_ns, 95) / 1e6
    p99 = _percentile(latencies_ns, 99) / 1e6
    mean = statistics.fmean(latencies_ns) / 1e6
    max_ms = latencies_ns[-1] / 1e6

    print(f"target={target} concurrency={concurrency} duration={elapsed:.2f}s")
    print(f"  rpcs:    {total} ({rps:,.0f} rps)")
    print(f"  errors:  {err_count}")
    print(f"  latency (ms): mean={mean:.3f} p50={p50:.3f} p95={p95:.3f} p99={p99:.3f} max={max_ms:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="pricing-grpc-service benchmark")
    parser.add_argument("--target", default="localhost:50051")
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--duration", type=float, default=5.0, help="measured window seconds")
    parser.add_argument("--warmup", type=float, default=1.0, help="warmup seconds")
    args = parser.parse_args()
    asyncio.run(run(args.target, args.concurrency, args.duration, args.warmup))


if __name__ == "__main__":
    main()
