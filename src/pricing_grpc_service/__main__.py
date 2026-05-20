"""CLI entry point: ``python -m pricing_grpc_service`` or ``pricing-grpc-service``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os

from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="pricing-grpc-service")
    parser.add_argument("--host", default=os.getenv("GRPC_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("GRPC_PORT", "50051"))
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for reproducible quotes (omit for non-deterministic)",
    )
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(serve(host=args.host, port=args.port, seed=args.seed))


if __name__ == "__main__":
    main()
