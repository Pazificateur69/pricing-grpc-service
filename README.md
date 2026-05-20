# pricing-grpc-service

[![ci](https://github.com/Pazificateur69/pricing-grpc-service/actions/workflows/ci.yml/badge.svg)](https://github.com/Pazificateur69/pricing-grpc-service/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Async **gRPC** pricing service in Python — a minimal but production-shaped
example of unary and server-streaming RPCs. Ships with a deterministic
in-memory quote engine (geometric Brownian motion) so it runs offline,
strict typing end-to-end, and a CI pipeline.

## RPC surface

```protobuf
service Pricing {
  rpc GetQuote(QuoteRequest) returns (Quote);                  // unary
  rpc StreamQuotes(StreamQuotesRequest) returns (stream Quote); // server streaming
}
```

Full schema in [`proto/pricing.proto`](proto/pricing.proto).

## Quickstart

```bash
git clone https://github.com/Pazificateur69/pricing-grpc-service.git
cd pricing-grpc-service
make install          # creates .venv and installs the package with dev extras
source .venv/bin/activate

make run              # terminal 1 — starts the gRPC server on :50051
make client           # terminal 2 — runs the example client
```

Expected output from the client:

```
snapshot BTC-USD: bid=68468.86 ask=68503.10 mid=68485.98
stream   BTC-USD: bid=68496.88 ask=68531.13
stream   ETH-USD: bid=3548.47  ask=3550.25
stream   BTC-USD: bid=68479.61 ask=68513.86
...
```

## CLI

```text
pricing-grpc-service [--host HOST] [--port PORT] [--seed SEED] [--log-level LEVEL]
```

Environment variables `GRPC_HOST`, `GRPC_PORT`, and `LOG_LEVEL` are honored as
defaults. Pass `--seed` to get reproducible quote sequences (useful for tests
and demos).

## Architecture

```
proto/pricing.proto                       protobuf contract
└── src/pricing_grpc_service/
    ├── generated/                        protoc output (checked in)
    ├── pricing_engine.py                 random-walk price simulator
    ├── service.py                        async PricingServicer (GetQuote, StreamQuotes)
    ├── server.py                         server bootstrap + graceful shutdown
    └── __main__.py                       CLI entry point
```

A few choices worth flagging:

- **`grpc.aio`** everywhere — the streaming RPC is a plain `async` generator,
  so back-pressure and cancellation use native asyncio semantics.
- **Graceful shutdown** on `SIGINT`/`SIGTERM`: in-flight streams get a grace
  period (default 2 s) before the server is torn down.
- **Input hardening**: `GetQuote` rejects empty symbols with
  `INVALID_ARGUMENT`; `StreamQuotes` clamps the requested interval to
  `[50 ms, 5 s]` and supports `max_updates` as a budget.
- **Deterministic engine**: seeding the RNG makes the entire RPC trajectory
  reproducible — critical for testing streaming behavior.

## Regenerating stubs

The generated `pricing_pb2*.py` files are checked in so the repo runs out of
the box. If you change `proto/pricing.proto`:

```bash
make proto
```

This invokes `grpc_tools.protoc` and rewrites the absolute import in
`pricing_pb2_grpc.py` to a package-relative one.

## Development

```bash
make check     # ruff + mypy --strict + pytest
make test
make lint
make typecheck
```

CI runs the same matrix on Python 3.11 / 3.12 / 3.13.

## What this isn't

This is a portfolio-grade example, not a production market data service.
There is no real exchange connectivity, no auth/TLS, no metrics export.
Adding them is straightforward (`grpc.ssl_server_credentials`,
[`grpc-interceptor`](https://pypi.org/project/grpc-interceptor/),
OpenTelemetry, etc.) — kept out of scope here to keep the code under ~200
lines of business logic.

## License

MIT — see [LICENSE](LICENSE).
