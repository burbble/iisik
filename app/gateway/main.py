from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from strawberry.fastapi import GraphQLRouter

from app.bootstrap import init_databases
from app.gateway.auth_client import AuthClient
from app.gateway.clients.factory import create_grpc_clients
from app.gateway.facade import ApplicationFacade
from app.gateway.schema import schema
from app.shared.errors import AuthenticationError


app = FastAPI(title="Profitability Analysis - Lab 7", version="0.7.0")


@app.on_event("startup")
def startup() -> None:
    init_databases()


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header:
        return None
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    return header.split(" ", 1)[1].strip()


def get_context(request: Request):
    token = _extract_bearer(request)
    actor = None
    if token:
        try:
            actor = AuthClient().verify(token)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {
        "facade": ApplicationFacade(create_grpc_clients()),
        "auth_client": AuthClient(),
        "actor": actor,
        "access_token": token,
    }


graphql_app = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_app, prefix="/graphql")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "lab": 6,
        "security": "jwt+redis",
        "integration": "grpc+kafka",
    }
