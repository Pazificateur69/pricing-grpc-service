"""Prometheus metrics for the gRPC server.

A single module so the Counter/Histogram/Gauge instances are shared across the
interceptor and the optional ``/metrics`` HTTP endpoint.
"""

from __future__ import annotations

import logging

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

# Use a dedicated registry so test runs don't collide with the default global one.
REGISTRY = CollectorRegistry()

RPC_TOTAL = Counter(
    "grpc_server_rpcs_total",
    "Total number of RPCs handled, labelled by method and grpc status code.",
    labelnames=("grpc_method", "grpc_code"),
    registry=REGISTRY,
)

RPC_LATENCY_SECONDS = Histogram(
    "grpc_server_rpc_duration_seconds",
    "Wall-clock duration of completed RPCs in seconds.",
    labelnames=("grpc_method",),
    buckets=(0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)

ACTIVE_STREAMS = Gauge(
    "grpc_server_active_streams",
    "Number of streaming RPCs currently in flight.",
    labelnames=("grpc_method",),
    registry=REGISTRY,
)


def start_metrics_server(port: int, host: str = "0.0.0.0") -> None:
    """Spawn the prometheus_client HTTP server in a background thread."""
    start_http_server(port=port, addr=host, registry=REGISTRY)
    logger.info("prometheus metrics endpoint on http://%s:%s/metrics", host, port)
