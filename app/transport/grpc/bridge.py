from __future__ import annotations

import json
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Callable

import grpc
from google.protobuf.wrappers_pb2 import StringValue

from app.config import (
    GRPC_MAX_ATTEMPTS,
    GRPC_RETRY_BACKOFF_SECONDS,
    GRPC_TIMEOUT_SECONDS,
)
from app.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.shared.logging_config import get_logger
from app.shared.resilience import RetryPolicy, call_grpc_with_retry

logger = get_logger("transport.grpc.bridge")


def to_jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "__dict__"):
        return {
            k: to_jsonable(v) for k, v in vars(value).items() if not k.startswith("_")
        }
    return str(value)


def _status_for(exc: Exception):
    if isinstance(exc, NotFoundError):
        return grpc.StatusCode.NOT_FOUND
    if isinstance(exc, ConflictError):
        return grpc.StatusCode.ALREADY_EXISTS
    if isinstance(exc, ValidationError):
        return grpc.StatusCode.INVALID_ARGUMENT
    if isinstance(exc, AuthenticationError):
        return grpc.StatusCode.UNAUTHENTICATED
    if isinstance(exc, AuthorizationError):
        return grpc.StatusCode.PERMISSION_DENIED
    return grpc.StatusCode.INTERNAL


def json_method(fn: Callable, operation: str):
    def handler(request: StringValue, context):
        started = time.perf_counter()
        try:
            payload = json.loads(request.value or "{}")
            result = fn(payload)
            logger.info(
                "gRPC server method completed",
                extra={
                    "operation": operation,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return StringValue(
                value=json.dumps(to_jsonable(result), ensure_ascii=False)
            )
        except Exception as exc:
            logger.exception(
                "gRPC server method failed",
                extra={
                    "operation": operation,
                    "error_type": type(exc).__name__,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            context.abort(_status_for(exc), str(exc))

    return handler


def add_json_service(
    server: grpc.Server, service_name: str, methods: dict[str, Callable]
):
    handlers = {}
    for method_name, fn in methods.items():
        handlers[method_name] = grpc.unary_unary_rpc_method_handler(
            json_method(fn, f"{service_name}.{method_name}"),
            request_deserializer=StringValue.FromString,
            response_serializer=StringValue.SerializeToString,
        )
    server.add_generic_rpc_handlers(
        (grpc.method_handlers_generic_handler(service_name, handlers),)
    )


class JsonGrpcClient:
    def __init__(
        self,
        target: str,
        service_name: str,
        timeout: float = GRPC_TIMEOUT_SECONDS,
        max_attempts: int = GRPC_MAX_ATTEMPTS,
        backoff_seconds: float = GRPC_RETRY_BACKOFF_SECONDS,
    ):
        self.target = target
        self.service_name = service_name
        self.policy = RetryPolicy(
            timeout_seconds=timeout,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
        )
        self.channel = grpc.insecure_channel(target)

    def call(self, method: str, payload: dict | None = None):
        rpc = self.channel.unary_unary(
            f"/{self.service_name}/{method}",
            request_serializer=StringValue.SerializeToString,
            response_deserializer=StringValue.FromString,
        )
        try:
            response = call_grpc_with_retry(
                rpc,
                StringValue(value=json.dumps(payload or {}, ensure_ascii=False)),
                operation=f"{self.service_name}.{method}",
                target=self.target,
                metadata=__import__(
                    "app.transport.grpc.security", fromlist=["rpc_metadata"]
                ).rpc_metadata(),
                policy=self.policy
                if method.startswith(("Get", "List", "Lookup"))
                or method == "ProfitabilitySummary"
                else RetryPolicy(
                    timeout_seconds=self.policy.timeout_seconds, max_attempts=1
                ),
            )
        except grpc.RpcError as exc:
            code = exc.code()
            message = exc.details() or "gRPC request failed"
            if code == grpc.StatusCode.NOT_FOUND:
                raise NotFoundError(message) from exc
            if code == grpc.StatusCode.ALREADY_EXISTS:
                raise ConflictError(message) from exc
            if code == grpc.StatusCode.INVALID_ARGUMENT:
                raise ValidationError(message) from exc
            if code == grpc.StatusCode.UNAUTHENTICATED:
                raise AuthenticationError(message) from exc
            if code == grpc.StatusCode.PERMISSION_DENIED:
                raise AuthorizationError(message) from exc
            raise RuntimeError(f"gRPC {self.service_name}.{method}: {message}") from exc
        return json.loads(response.value or "null")
