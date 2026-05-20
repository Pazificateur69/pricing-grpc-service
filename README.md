# pricing-grpc-service

[![ci](https://github.com/Pazificateur69/pricing-grpc-service/actions/workflows/ci.yml/badge.svg)](https://github.com/Pazificateur69/pricing-grpc-service/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Async **gRPC** pricing service in Python — a compact but production-shaped
example. Unary + server-streaming RPCs, standard health checking, server
reflection, Prometheus metrics, TLS / mTLS, structured logging, a benchmark
harness, and a Docker image. Deterministic in-memory quote engine (geometric
Brownian motion) so the whole stack runs offline.

## RPC surface

```protobuf
service Pricing {
  rpc GetQuote(QuoteRequest) returns (Quote);                   // unary
  rpc StreamQuotes(StreamQuotesRequest) returns (stream Quote);  // server streaming
  rpc ListSymbols(ListSymbolsRequest) returns (ListSymbolsResponse);
}
```

The server also exposes:

| Service | Purpose |
| --- | --- |
| `grpc.health.v1.Health`               | Kubernetes / load balancer probes |
| `grpc.reflection.v1alpha.ServerReflection` | Lets `grpcurl`, Postman, Evans discover the schema |
| `GET /metrics` on `:9090`             | Prometheus exposition (counter, histogram, gauge) |

Full proto in [`proto/pricing.proto`](proto/pricing.proto).

## Quickstart

```bash
git clone https://github.com/Pazificateur69/pricing-grpc-service.git
cd pricing-grpc-service
make install                # creates .venv with dev extras
source .venv/bin/activate

make run                    # terminal 1 — gRPC :50051, metrics :9090
make client                 # terminal 2 — demo client
make bench                  # terminal 2 — latency / throughput benchmark
```

Example client output:

```
symbols: AAPL, BTC-USD, ETH-USD, EUR-USD, SOL-USD, TSLA, USD-JPY
snapshot BTC-USD: bid=68468.86 ask=68503.10 mid=68485.98
stream   BTC-USD: bid=68496.88 ask=68531.13
stream   ETH-USD: bid=3548.47  ask=3550.25
...
```

## With grpcurl (reflection works out of the box)

```bash
grpcurl -plaintext localhost:50051 list
# grpc.health.v1.Health
# grpc.reflection.v1alpha.ServerReflection
# pricing.v1.Pricing

grpcurl -plaintext -d '{"symbol":"BTC-USD"}' localhost:50051 pricing.v1.Pricing/GetQuote
grpcurl -plaintext localhost:50051 grpc.health.v1.Health/Check
```

## CLI

```text
pricing-grpc-service [--host HOST] [--port PORT] [--seed SEED] [--log-level LEVEL]
                     [--tls-cert PATH --tls-key PATH [--tls-client-ca PATH]]
                     [--metrics-port PORT]
```

Env defaults: `GRPC_HOST`, `GRPC_PORT`, `LOG_LEVEL`, `METRICS_PORT`,
`TLS_CERT`, `TLS_KEY`, `TLS_CLIENT_CA`. Passing both `--tls-cert` and
`--tls-key` switches to `grpcs://`; adding `--tls-client-ca` enables mTLS.

## Architecture

```
proto/pricing.proto                        protobuf contract
src/pricing_grpc_service/
├── generated/                              protoc output (checked in)
├── pricing_engine.py                       random-walk price simulator
├── service.py                              async PricingServicer
├── interceptors.py                         logging + Prometheus interceptor
├── metrics.py                              counters / histogram / gauge + HTTP exporter
├── server.py                               bootstrap: TLS, health, reflection, shutdown
└── __main__.py                             CLI entry point
bench/bench.py                              p50/p95/p99 latency harness
examples/client.py                          demo client
deploy/prometheus.yml                       Prometheus scrape config
Dockerfile / docker-compose.yml             multi-stage image + Prometheus side-car
```

Design highlights:

- **`grpc.aio`** everywhere — streaming RPCs are plain `async` generators, so
  back-pressure and cancellation use native asyncio semantics.
- **One observability interceptor** wraps every method, including streams,
  to record latency, status code, and active-stream gauge.
- **Graceful shutdown** on `SIGINT`/`SIGTERM`: the health service flips to
  `NOT_SERVING` (so load balancers stop sending traffic), then the server
  drains for a configurable grace period.
- **Input hardening**: `GetQuote` rejects empty symbols with
  `INVALID_ARGUMENT`; `StreamQuotes` clamps the requested interval to
  `[50 ms, 5 s]` and supports `max_updates` as a budget.
- **Deterministic engine**: seeding the RNG makes the whole RPC trajectory
  reproducible — critical for testing streaming behavior and benchmarks.
- **TLS / mTLS optional, off by default** — flip on by passing the cert
  paths; nothing else changes for callers besides the channel scheme.

## Observability

Each handler emits:

| Metric | Type | Labels |
| --- | --- | --- |
| `grpc_server_rpcs_total`              | Counter   | `grpc_method`, `grpc_code` |
| `grpc_server_rpc_duration_seconds`    | Histogram | `grpc_method` |
| `grpc_server_active_streams`          | Gauge     | `grpc_method` |

Tail one of the histograms with `curl -s localhost:9090/metrics | grep
grpc_server_rpc_duration_seconds`.

## Benchmark

```bash
make run &                                              # in another shell
python bench/bench.py --concurrency 64 --duration 10
```

```
target=localhost:50051 concurrency=64 duration=10.00s
  rpcs:    231,184 (23,118 rps)
  errors:  0
  latency (ms): mean=2.762 p50=2.510 p95=4.812 p99=8.103 max=29.443
```

Numbers above are illustrative — actual figures depend on hardware. The
script is deliberately small (~90 lines) so it's easy to adapt.

## Docker

```bash
make docker-up         # gRPC :50051, Prometheus UI :9091
make docker-down
```

The image is multi-stage and runs as a non-root user (`uid 10001`). Compose
brings up a Prometheus side-car already configured to scrape the service.

## Regenerating stubs

The generated `pricing_pb2*.py` files are checked in so the repo runs out of
the box. After editing `proto/pricing.proto`:

```bash
make proto
```

This invokes `grpc_tools.protoc` and rewrites the absolute import in
`pricing_pb2_grpc.py` to a package-relative one.

## Development

```bash
make check         # ruff + mypy --strict + pytest
make precommit     # run all pre-commit hooks
```

CI runs the same matrix on Python 3.11 / 3.12 / 3.13, plus a Docker image
build.

## License

MIT — see [LICENSE](LICENSE).
