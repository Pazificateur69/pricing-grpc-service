"""Minimal demo client. Run after the server is up on localhost:50051."""

from __future__ import annotations

import asyncio

import grpc

from pricing_grpc_service.generated import pricing_pb2, pricing_pb2_grpc


async def main() -> None:
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = pricing_pb2_grpc.PricingStub(channel)

        snapshot = await stub.GetQuote(pricing_pb2.QuoteRequest(symbol="BTC-USD"))
        print(
            f"snapshot {snapshot.symbol}: "
            f"bid={snapshot.bid:.4f} ask={snapshot.ask:.4f} mid={snapshot.mid:.4f}"
        )

        request = pricing_pb2.StreamQuotesRequest(
            symbols=["BTC-USD", "ETH-USD"],
            interval_ms=250,
            max_updates=6,
        )
        async for quote in stub.StreamQuotes(request):
            print(f"stream   {quote.symbol}: bid={quote.bid:.4f} ask={quote.ask:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
