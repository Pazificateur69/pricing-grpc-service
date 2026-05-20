"""Async gRPC server interceptors: structured logging + Prometheus metrics.

All four RPC patterns are instrumented (unary-unary, unary-stream,
stream-unary, stream-stream). We measure wall-clock duration end-to-end,
record the gRPC status code, and track active streams so dashboards can spot
fan-out or connection leaks.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import grpc

from .metrics import ACTIVE_STREAMS, RPC_LATENCY_SECONDS, RPC_TOTAL

logger = logging.getLogger(__name__)

Continuation = Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler | None]]


def _code_from_exception(exc: BaseException) -> grpc.StatusCode:
    """Best-effort extraction of the StatusCode from an aborted RPC."""
    code = getattr(exc, "code", None)
    if callable(code):
        try:
            value = code()
        except Exception:
            return grpc.StatusCode.UNKNOWN
        if isinstance(value, grpc.StatusCode):
            return value
    return grpc.StatusCode.UNKNOWN


class ObservabilityInterceptor(grpc.aio.ServerInterceptor):  # type: ignore[misc]
    """Wrap every handler to emit logs + Prometheus metrics."""

    async def intercept_service(
        self,
        continuation: Continuation,
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler | None:
        handler = await continuation(handler_call_details)
        if handler is None:
            return None
        method = handler_call_details.method

        if handler.unary_unary is not None:
            return self._wrap_unary_unary(method, handler)
        if handler.unary_stream is not None:
            return self._wrap_unary_stream(method, handler)
        if handler.stream_unary is not None:
            return self._wrap_stream_unary(method, handler)
        if handler.stream_stream is not None:
            return self._wrap_stream_stream(method, handler)
        return handler

    # ----- unary-unary -----
    def _wrap_unary_unary(
        self, method: str, handler: grpc.RpcMethodHandler
    ) -> grpc.RpcMethodHandler:
        inner = handler.unary_unary

        async def wrapper(request: Any, context: grpc.aio.ServicerContext) -> Any:
            start = time.perf_counter()
            code = grpc.StatusCode.OK
            try:
                return await inner(request, context)
            except grpc.aio.AbortError as exc:
                code = _code_from_exception(exc)
                raise
            except Exception:
                code = grpc.StatusCode.INTERNAL
                raise
            finally:
                self._record(method, code, time.perf_counter() - start)

        return grpc.unary_unary_rpc_method_handler(
            wrapper,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )

    # ----- unary-stream -----
    def _wrap_unary_stream(
        self, method: str, handler: grpc.RpcMethodHandler
    ) -> grpc.RpcMethodHandler:
        inner = handler.unary_stream

        async def wrapper(
            request: Any, context: grpc.aio.ServicerContext
        ) -> AsyncIterator[Any]:
            async for response in self._instrument_stream(method, inner(request, context)):
                yield response

        return grpc.unary_stream_rpc_method_handler(
            wrapper,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )

    # ----- stream-unary -----
    def _wrap_stream_unary(
        self, method: str, handler: grpc.RpcMethodHandler
    ) -> grpc.RpcMethodHandler:
        inner = handler.stream_unary

        async def wrapper(
            request_iterator: AsyncIterator[Any], context: grpc.aio.ServicerContext
        ) -> Any:
            start = time.perf_counter()
            code = grpc.StatusCode.OK
            try:
                return await inner(request_iterator, context)
            except grpc.aio.AbortError as exc:
                code = _code_from_exception(exc)
                raise
            except Exception:
                code = grpc.StatusCode.INTERNAL
                raise
            finally:
                self._record(method, code, time.perf_counter() - start)

        return grpc.stream_unary_rpc_method_handler(
            wrapper,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )

    # ----- stream-stream -----
    def _wrap_stream_stream(
        self, method: str, handler: grpc.RpcMethodHandler
    ) -> grpc.RpcMethodHandler:
        inner = handler.stream_stream

        async def wrapper(
            request_iterator: AsyncIterator[Any], context: grpc.aio.ServicerContext
        ) -> AsyncIterator[Any]:
            async for response in self._instrument_stream(
                method, inner(request_iterator, context)
            ):
                yield response

        return grpc.stream_stream_rpc_method_handler(
            wrapper,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )

    # ----- helpers -----
    async def _instrument_stream(
        self, method: str, source: AsyncIterator[Any]
    ) -> AsyncIterator[Any]:
        ACTIVE_STREAMS.labels(grpc_method=method).inc()
        start = time.perf_counter()
        code = grpc.StatusCode.OK
        messages = 0
        try:
            async for item in source:
                messages += 1
                yield item
        except grpc.aio.AbortError as exc:
            code = _code_from_exception(exc)
            raise
        except Exception:
            code = grpc.StatusCode.INTERNAL
            raise
        finally:
            elapsed = time.perf_counter() - start
            self._record(method, code, elapsed, messages=messages, streaming=True)
            ACTIVE_STREAMS.labels(grpc_method=method).dec()

    @staticmethod
    def _record(
        method: str,
        code: grpc.StatusCode,
        elapsed_s: float,
        *,
        messages: int | None = None,
        streaming: bool = False,
    ) -> None:
        RPC_LATENCY_SECONDS.labels(grpc_method=method).observe(elapsed_s)
        RPC_TOTAL.labels(grpc_method=method, grpc_code=code.name).inc()
        if streaming:
            logger.info(
                "rpc method=%s code=%s duration_ms=%.2f messages=%s",
                method, code.name, elapsed_s * 1000, messages,
            )
        else:
            logger.info(
                "rpc method=%s code=%s duration_ms=%.2f",
                method, code.name, elapsed_s * 1000,
            )
