"""Authenticated internal RPC boundary. Only gateway may invoke business mutations."""

import os
import secrets
from datetime import datetime, timedelta, timezone

import grpc
import jwt

# Per-process ephemeral key is suitable only for the in-process test runtime.
# Separate production processes must share INTERNAL_JWT_SECRET from their environment.
_SECRET = os.getenv("INTERNAL_JWT_SECRET") or secrets.token_urlsafe(48)
if len(_SECRET) < 32:
    raise RuntimeError("INTERNAL_JWT_SECRET must contain at least 32 characters")
_READERS = {"gateway", "costing", "analytics", "production", "financial", "reporting"}


def rpc_metadata(identity=None):
    identity = identity or os.getenv("RPC_SERVICE_ID", "gateway")
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": identity,
            "role": "INTERNAL_SERVICE",
            "iss": "profitability-internal",
            "aud": "internal-rpc",
            "iat": now,
            "exp": now + timedelta(minutes=2),
        },
        _SECRET,
        algorithm="HS256",
    )
    return (("authorization", f"Bearer {token}"),)


class InternalAuthorization(grpc.ServerInterceptor):
    def intercept_service(self, continuation, details):
        handler = continuation(details)
        if handler is None or handler.unary_unary is None:
            return handler
        metadata = dict(details.invocation_metadata)

        def checked(request, context):
            try:
                raw = metadata.get("authorization", "")
                if not raw.startswith("Bearer "):
                    raise ValueError("Missing service JWT")
                claims = jwt.decode(
                    raw[7:],
                    _SECRET,
                    algorithms=["HS256"],
                    audience="internal-rpc",
                    issuer="profitability-internal",
                    options={"require": ["sub", "role", "iat", "exp", "aud", "iss"]},
                )
                if (
                    claims["role"] != "INTERNAL_SERVICE"
                    or claims["sub"] not in _READERS
                ):
                    context.abort(
                        grpc.StatusCode.PERMISSION_DENIED, "Service role is not allowed"
                    )
            except (jwt.PyJWTError, ValueError):
                context.abort(
                    grpc.StatusCode.UNAUTHENTICATED,
                    "Valid internal service JWT required",
                )
            method = details.method.rsplit("/", 1)[-1]
            readonly = (
                method.startswith(("Get", "List", "Lookup"))
                or method == "ProfitabilitySummary"
            )
            if not readonly and claims["sub"] != "gateway":
                context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    "Only gateway may initiate mutations",
                )
            return handler.unary_unary(request, context)

        return grpc.unary_unary_rpc_method_handler(
            checked,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )
