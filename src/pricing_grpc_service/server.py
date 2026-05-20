"""gRPC server bootstrap with graceful shutdown, TLS, health, reflection, metrics."""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from .generated import pricing_pb2, pricing_pb2_grpc
from .interceptors import ObservabilityInterceptor
from .metrics import start_metrics_server
from .pricing_engine import PricingEngine
from .service import PricingServicer

logger = logging.getLogger(__name__)

PRICING_SERVICE_NAME = pricing_pb2.DESCRIPTOR.services_by_name["Pricing"].full_name


def _build_server_credentials(
    cert_path: Path,
    key_path: Path,
    client_ca_path: Path | None,
) -> grpc.ServerCredentials:
    cert = cert_path.read_bytes()
    key = key_path.read_bytes()
    if client_ca_path is not None:
        return grpc.ssl_server_credentials(
            [(key, cert)],
            root_certificates=client_ca_path.read_bytes(),
            require_client_auth=True,
        )
    return grpc.ssl_server_credentials([(key, cert)])


async def serve(
    *,
    host: str = "0.0.0.0",
    port: int = 50051,
    seed: int | None = None,
    shutdown_grace_s: float = 2.0,
    tls_cert: Path | None = None,
    tls_key: Path | None = None,
    tls_client_ca: Path | None = None,
    metrics_port: int | None = 9090,
) -> None:
    server = grpc.aio.server(interceptors=(ObservabilityInterceptor(),))

    # Application service.
    pricing_pb2_grpc.add_PricingServicer_to_server(  # type: ignore[no-untyped-call]
        PricingServicer(PricingEngine(seed=seed)), server
    )

    # Standard health checking — k8s and load balancers expect this.
    health_servicer = health.aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    await health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    await health_servicer.set(PRICING_SERVICE_NAME, health_pb2.HealthCheckResponse.SERVING)

    # Server reflection — lets grpcurl/Postman discover the schema at runtime.
    reflection.enable_server_reflection(
        (
            PRICING_SERVICE_NAME,
            reflection.SERVICE_NAME,
            health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
        ),
        server,
    )

    # Bind socket.
    listen_addr = f"{host}:{port}"
    if tls_cert and tls_key:
        creds = _build_server_credentials(tls_cert, tls_key, tls_client_ca)
        server.add_secure_port(listen_addr, creds)
        scheme = "grpcs"
    elif tls_cert or tls_key:
        raise ValueError("--tls-cert and --tls-key must be provided together")
    else:
        server.add_insecure_port(listen_addr)
        scheme = "grpc"

    await server.start()
    logger.info("pricing-grpc-service listening on %s://%s", scheme, listen_addr)
    logger.info(
        "services: %s, grpc.health.v1.Health, grpc.reflection.v1alpha.ServerReflection",
        PRICING_SERVICE_NAME,
    )

    if metrics_port is not None:
        start_metrics_server(port=metrics_port, host=host)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    logger.info("shutdown signal received, draining (grace=%ss)", shutdown_grace_s)
    await health_servicer.enter_graceful_shutdown()
    await server.stop(grace=shutdown_grace_s)
