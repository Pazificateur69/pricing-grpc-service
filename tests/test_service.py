"""End-to-end tests against a live in-process gRPC server."""

from __future__ import annotations

from collections.abc import AsyncIterator

import grpc
import pytest
import pytest_asyncio

from pricing_grpc_service.generated import pricing_pb2, pricing_pb2_grpc
from pricing_grpc_service.pricing_engine import PricingEngine
from pricing_grpc_service.service import PricingServicer


@pytest_asyncio.fixture
async def channel() -> AsyncIterator[grpc.aio.Channel]:
    server = grpc.aio.server()
    pricing_pb2_grpc.add_PricingServicer_to_server(
        PricingServicer(PricingEngine(seed=42)), server
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


def test_engine_is_deterministic_with_seed() -> None:
    a = PricingEngine(seed=123)
    b = PricingEngine(seed=123)
    for symbol in ("BTC-USD", "ETH-USD"):
        for _ in range(5):
            assert a.quote(symbol).mid == b.quote(symbol).mid
