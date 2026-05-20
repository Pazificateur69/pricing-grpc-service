"""End-to-end tests against a live in-process gRPC server."""

from __future__ import annotations

from collections.abc import AsyncIterator

import grpc
import pytest
import pytest_asyncio
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection, reflection_pb2, reflection_pb2_grpc

from pricing_grpc_service.generated import pricing_pb2, pricing_pb2_grpc
from pricing_grpc_service.interceptors import ObservabilityInterceptor
from pricing_grpc_service.metrics import RPC_TOTAL
from pricing_grpc_service.pricing_engine import PricingEngine
from pricing_grpc_service.service import PricingServicer

PRICING_FULL_NAME = pricing_pb2.DESCRIPTOR.services_by_name["Pricing"].full_name


@pytest_asyncio.fixture
async def channel() -> AsyncIterator[grpc.aio.Channel]:
    server = grpc.aio.server(interceptors=(ObservabilityInterceptor(),))
    pricing_pb2_grpc.add_PricingServicer_to_server(
        PricingServicer(PricingEngine(seed=42)), server
    )
    health_servicer = health.aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    await health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    await health_servicer.set(PRICING_FULL_NAME, health_pb2.HealthCheckResponse.SERVING)
    reflection.enable_server_reflection(
        (PRICING_FULL_NAME, reflection.SERVICE_NAME), server
    )
    port = server.add_insecure_port("[::]:0")
    await server.start()
    ch = grpc.aio.insecure_channel(f"localhost:{port}")
    try:
        yield ch
    finally:
        await ch.close()
        await server.stop(grace=None)


async def test_get_quote_returns_snapshot(channel: grpc.aio.Channel) -> None:
    stub = pricing_pb2_grpc.PricingStub(channel)
    quote = await stub.GetQuote(pricing_pb2.QuoteRequest(symbol="BTC-USD"))
    assert quote.symbol == "BTC-USD"
    assert quote.bid < quote.mid < quote.ask
    assert quote.timestamp_ns > 0


async def test_get_quote_normalizes_symbol(channel: grpc.aio.Channel) -> None:
    stub = pricing_pb2_grpc.PricingStub(channel)
    quote = await stub.GetQuote(pricing_pb2.QuoteRequest(symbol="btc-usd"))
    assert quote.symbol == "BTC-USD"


async def test_get_quote_rejects_empty_symbol(channel: grpc.aio.Channel) -> None:
    stub = pricing_pb2_grpc.PricingStub(channel)
    with pytest.raises(grpc.RpcError) as exc:
        await stub.GetQuote(pricing_pb2.QuoteRequest(symbol=""))
    assert exc.value.code() == grpc.StatusCode.INVALID_ARGUMENT


async def test_stream_quotes_respects_budget(channel: grpc.aio.Channel) -> None:
    stub = pricing_pb2_grpc.PricingStub(channel)
    request = pricing_pb2.StreamQuotesRequest(
        symbols=["BTC-USD", "ETH-USD"],
        interval_ms=50,
        max_updates=4,
    )
    quotes = [q async for q in stub.StreamQuotes(request)]
    assert len(quotes) == 4
    assert {q.symbol for q in quotes} == {"BTC-USD", "ETH-USD"}


async def test_stream_quotes_rejects_empty_symbols(channel: grpc.aio.Channel) -> None:
    stub = pricing_pb2_grpc.PricingStub(channel)
    stream = stub.StreamQuotes(pricing_pb2.StreamQuotesRequest(symbols=[]))
    with pytest.raises(grpc.RpcError) as exc:
        async for _ in stream:
            pass
    assert exc.value.code() == grpc.StatusCode.INVALID_ARGUMENT


async def test_list_symbols_returns_defaults(channel: grpc.aio.Channel) -> None:
    stub = pricing_pb2_grpc.PricingStub(channel)
    response = await stub.ListSymbols(pricing_pb2.ListSymbolsRequest())
    assert "BTC-USD" in response.symbols
    assert "ETH-USD" in response.symbols


async def test_health_check_reports_serving(channel: grpc.aio.Channel) -> None:
    stub = health_pb2_grpc.HealthStub(channel)
    overall = await stub.Check(health_pb2.HealthCheckRequest())
    assert overall.status == health_pb2.HealthCheckResponse.SERVING
    specific = await stub.Check(health_pb2.HealthCheckRequest(service=PRICING_FULL_NAME))
    assert specific.status == health_pb2.HealthCheckResponse.SERVING


async def test_reflection_lists_services(channel: grpc.aio.Channel) -> None:
    stub = reflection_pb2_grpc.ServerReflectionStub(channel)

    async def requests() -> AsyncIterator[reflection_pb2.ServerReflectionRequest]:
        yield reflection_pb2.ServerReflectionRequest(list_services="")

    responses = [r async for r in stub.ServerReflectionInfo(requests())]
    assert responses, "expected at least one reflection response"
    services = {svc.name for svc in responses[0].list_services_response.service}
    assert PRICING_FULL_NAME in services


async def test_metrics_counter_increments(channel: grpc.aio.Channel) -> None:
    method = f"/{PRICING_FULL_NAME}/GetQuote"
    before = RPC_TOTAL.labels(grpc_method=method, grpc_code="OK")._value.get()
    stub = pricing_pb2_grpc.PricingStub(channel)
    await stub.GetQuote(pricing_pb2.QuoteRequest(symbol="BTC-USD"))
    after = RPC_TOTAL.labels(grpc_method=method, grpc_code="OK")._value.get()
    assert after == before + 1


def test_engine_is_deterministic_with_seed() -> None:
    a = PricingEngine(seed=123)
    b = PricingEngine(seed=123)
    for symbol in ("BTC-USD", "ETH-USD"):
        for _ in range(5):
            assert a.quote(symbol).mid == b.quote(symbol).mid


def test_engine_known_symbols_includes_defaults() -> None:
    assert "BTC-USD" in PricingEngine().known_symbols()
