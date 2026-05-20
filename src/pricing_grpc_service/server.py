"""gRPC server bootstrap with graceful shutdown."""

from __future__ import annotations

import asyncio
import logging
import signal

import grpc

from .generated import pricing_pb2_grpc
from .pricing_engine import PricingEngine
from .service import PricingServicer

logger = logging.getLogger(__name__)


async def serve(
    *,
    host: str = "0.0.0.0",
    port: int = 50051,
    seed: int | None = None,
    shutdown_grace_s: float = 2.0,
) -> None:
    server = grpc.aio.server()
    servicer = PricingServicer(PricingEngine(seed=seed))
    pricing_pb2_grpc.add_PricingServicer_to_server(servicer, server)  # type: ignore[no-untyped-call]

    listen_addr = f"{host}:{port}"
    server.add_insecure_port(listen_addr)
    await server.start()
    logger.info("pricing-grpc-service listening on %s", listen_addr)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    logger.info("shutdown signal received, draining (grace=%ss)", shutdown_grace_s)
    await server.stop(grace=shutdown_grace_s)
