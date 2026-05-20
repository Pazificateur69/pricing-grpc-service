"""In-memory pricing engine driven by a geometric Brownian motion random walk."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from time import time_ns
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    mid: float
    timestamp_ns: int


class PricingEngine:
    """Random-walk pricing engine. Not for production trading.

    Each call to :meth:`quote` advances the price for the requested symbol by
    one geometric Brownian motion step, then returns a Quote with a synthetic
    bid/ask spread. Deterministic when ``seed`` is provided.
    """

    DEFAULT_SEEDS: ClassVar[dict[str, float]] = {
        "BTC-USD": 68_500.0,
        "ETH-USD": 3_550.0,
        "SOL-USD": 152.0,
        "EUR-USD": 1.085,
        "USD-JPY": 156.4,
        "AAPL": 188.5,
        "TSLA": 245.0,
    }

    def __init__(
        self,
        *,
        spread_bps: float = 5.0,
        volatility: float = 0.0008,
        seed: int | None = None,
    ) -> None:
        if spread_bps < 0:
            raise ValueError("spread_bps must be non-negative")
        if volatility < 0:
            raise ValueError("volatility must be non-negative")
        self._prices: dict[str, float] = dict(self.DEFAULT_SEEDS)
        self._spread: float = spread_bps / 10_000.0
        self._vol: float = volatility
        self._rng: random.Random = random.Random(seed)

    def known_symbols(self) -> list[str]:
        return sorted(self._prices)

    def quote(self, symbol: str) -> Quote:
        normalized = symbol.upper()
        # Bootstrap unknown symbols at $100 so client probing still works.
        self._prices.setdefault(normalized, 100.0)
        mid = self._step(normalized)
        half_spread = mid * self._spread / 2
        return Quote(
            symbol=normalized,
            bid=mid - half_spread,
            ask=mid + half_spread,
            mid=mid,
            timestamp_ns=time_ns(),
        )

    def _step(self, symbol: str) -> float:
        prev = self._prices[symbol]
        shock = math.exp(self._rng.gauss(0.0, self._vol))
        nxt = max(prev * shock, 1e-4)
        self._prices[symbol] = nxt
        return nxt
