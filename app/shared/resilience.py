from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

import grpc

from app.config import GRPC_MAX_ATTEMPTS, GRPC_RETRY_BACKOFF_SECONDS, GRPC_TIMEOUT_SECONDS
from app.shared.logging_config import get_logger

T = TypeVar("T")
logger = get_logger("resilience.grpc")

TRANSIENT_GRPC_CODES = {
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
    grpc.StatusCode.RESOURCE_EXHAUSTED,
    grpc.StatusCode.ABORTED,
}


@dataclass(frozen=True)
class RetryPolicy:
    timeout_seconds: float = GRPC_TIMEOUT_SECONDS
    max_attempts: int = GRPC_MAX_ATTEMPTS
    backoff_seconds: float = GRPC_RETRY_BACKOFF_SECONDS


def call_grpc_with_retry(
    rpc: Callable[..., T],
    request,
    *,
    operation: str,
    target: str,
    policy: RetryPolicy | None = None,
    metadata=None,
) -> T:
    policy = policy or RetryPolicy()
    last_error: grpc.RpcError | None = None
    for attempt in range(1, policy.max_attempts + 1):
        started = time.perf_counter()
        try:
            response = rpc(request, timeout=policy.timeout_seconds, metadata=metadata)
            logger.info(
                "gRPC call completed",
                extra={
                    "operation": operation,
                    "target": target,
                    "attempt": attempt,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return response
        except grpc.RpcError as exc:
            last_error = exc
            code = exc.code()
            retryable = code in TRANSIENT_GRPC_CODES and attempt < policy.max_attempts
            logger.warning(
                "gRPC call failed%s" % (", retrying" if retryable else ""),
                extra={
                    "operation": operation,
                    "target": target,
                    "attempt": attempt,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "error_type": str(code),
                },
            )
            if not retryable:
                raise
            time.sleep(policy.backoff_seconds * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error
