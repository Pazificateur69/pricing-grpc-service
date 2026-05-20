"""CLI entry point: ``python -m pricing_grpc_service`` or ``pricing-grpc-service``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

from .server import serve


def _env_path(name: str) -> Path | None:
    value = os.getenv(name)
    return Path(value) if value else None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pricing-grpc-service")
    parser.add_argument("--host", default=os.getenv("GRPC_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("GRPC_PORT", "50051")))
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for reproducible quotes (omit for non-deterministic)",
    )
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))

    tls_group = parser.add_argument_group("TLS")
    tls_group.add_argument(
        "--tls-cert",
        type=Path,
        default=_env_path("TLS_CERT"),
        help="PEM server certificate. Required together with --tls-key.",
    )
    tls_group.add_argument(
        "--tls-key",
        type=Path,
        default=_env_path("TLS_KEY"),
        help="PEM private key for the server certificate.",
    )
    tls_group.add_argument(
        "--tls-client-ca",
        type=Path,
        default=_env_path("TLS_CLIENT_CA"),
        help="PEM CA bundle. If set, the server requires client certs (mTLS).",
    )

    obs_group = parser.add_argument_group("observability")
    obs_group.add_argument(
        "--metrics-port",
        type=int,
        default=int(os.getenv("METRICS_PORT", "9090")),
        help="Prometheus /metrics HTTP port. Set to 0 to disable.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    metrics_port = args.metrics_port if args.metrics_port > 0 else None
    asyncio.run(
        serve(
            host=args.host,
            port=args.port,
            seed=args.seed,
            tls_cert=args.tls_cert,
            tls_key=args.tls_key,
            tls_client_ca=args.tls_client_ca,
            metrics_port=metrics_port,
        )
    )


if __name__ == "__main__":
    main()
