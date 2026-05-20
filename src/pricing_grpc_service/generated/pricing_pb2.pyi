from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class QuoteRequest(_message.Message):
    __slots__ = ("symbol",)
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    def __init__(self, symbol: _Optional[str] = ...) -> None: ...

class StreamQuotesRequest(_message.Message):
    __slots__ = ("symbols", "interval_ms", "max_updates")
    SYMBOLS_FIELD_NUMBER: _ClassVar[int]
    INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    MAX_UPDATES_FIELD_NUMBER: _ClassVar[int]
    symbols: _containers.RepeatedScalarFieldContainer[str]
    interval_ms: int
    max_updates: int
    def __init__(self, symbols: _Optional[_Iterable[str]] = ..., interval_ms: _Optional[int] = ..., max_updates: _Optional[int] = ...) -> None: ...

class Quote(_message.Message):
    __slots__ = ("symbol", "bid", "ask", "mid", "timestamp_ns")
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    BID_FIELD_NUMBER: _ClassVar[int]
    ASK_FIELD_NUMBER: _ClassVar[int]
    MID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_NS_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    bid: float
    ask: float
    mid: float
    timestamp_ns: int
    def __init__(self, symbol: _Optional[str] = ..., bid: _Optional[float] = ..., ask: _Optional[float] = ..., mid: _Optional[float] = ..., timestamp_ns: _Optional[int] = ...) -> None: ...
