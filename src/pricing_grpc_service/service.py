"""Async gRPC servicer for the pricing service."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import grpc

from .generated import pricing_pb2, pricing_pb2_grpc
from .pricing_engine import PricingEngine, Quote

logger = logging.getLogger(__name__)


def _to_pb(quote: Quote) -> pricing_pb2.Quote:
    return pricing_pb2.Quote(
        symbol=quote.symbol,
        bid=quote.bid,
        ask=quote.ask,
        mid=quote.mid,
        timestamp_ns=quote.timestamp_ns,
    )


class PricingServicer(pricing_pb2_grpc.PricingServicer):
    MIN_INTERVAL_MS = 50
    MAX_INTERVAL_MS = 5_000
    DEFAULT_INTERVAL_MS = 500

    def __init__(self, engine: PricingEngine) -> None:
        self._engine = engine

    async def GetQuote(
        self,
        request: pricing_pb2.QuoteRequest,
        context: grpc.aio.ServicerContext,
    ) -> pricing_pb2.Quote:
        if not request.symbol:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "symbol is required")
        return _to_pb(self._engine.quote(request.symbol))

    async def StreamQuotes(
        self,
        request: pricing_pb2.StreamQuotesRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[pricing_pb2.Quote]:
        symbols = [s for s in request.symbols if s]
        if not symbols:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "at least one symbol is required"
            )

        requested = request.interval_ms or self.DEFAULT_INTERVAL_MS
        interval_ms = max(self.MIN_INTERVAL_MS, min(requested, self.MAX_INTERVAL_MS))
        interval_s = interval_ms / 1_000.0
        budget = request.max_updates  # 0 -> unbounded

        peer = context.peer()
        logger.info(
            "stream start peer=%s symbols=%s interval_ms=%s max_updates=%s",
            peer, symbols, interval_ms, budget or "unbounded",
        )
        sent = 0
        try:
            while True:
                for symbol in symbols:
                    yield _to_pb(self._engine.quote(symbol))
                    sent += 1
                    if budget and sent >= budget:
                        return
                await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            logger.info("stream cancelled peer=%s sent=%s", peer, sent)
            raise
        finally:
            logger.info("stream end peer=%s sent=%s", peer, sent)

    async def ListSymbols(
        self,
        request: pricing_pb2.ListSymbolsRequest,
        context: grpc.aio.ServicerContext,
    ) -> pricing_pb2.ListSymbolsResponse:
        del request, context  # empty request by contract
        return pricing_pb2.ListSymbolsResponse(symbols=self._engine.known_symbols())
