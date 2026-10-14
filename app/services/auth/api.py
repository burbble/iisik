from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.bootstrap import init_databases
from app.shared.errors import AuthenticationError, ConflictError, ValidationError

from .dependencies import get_auth_service
from .service import AuthService


app = FastAPI(title="Profitability Auth Service - Lab 7", version="0.7.0")


@app.on_event("startup")
def startup() -> None:
    init_databases()


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: str
    email: str
    roles: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: str
    user: UserResponse


def bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    return authorization.split(" ", 1)[1].strip()


@app.post("/auth/register", response_model=UserResponse, status_code=201)
def register(body: Credentials, auth: AuthService = Depends(get_auth_service)):
    try:
        actor = auth.register(body.email, body.password)
        return UserResponse(id=actor.user_id, email=actor.email, roles=list(actor.roles))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/auth/login", response_model=LoginResponse)
def login(body: Credentials, auth: AuthService = Depends(get_auth_service)):
    try:
        result = auth.login(body.email, body.password)
        return LoginResponse(
            access_token=result.access_token,
            token_type=result.token_type,
            expires_at=result.expires_at.isoformat(),
            user=UserResponse(
                id=result.actor.user_id,
                email=result.actor.email,
                roles=list(result.actor.roles),
            ),
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/auth/verify", response_model=UserResponse)
def verify(
    token: str = Depends(bearer_token),
    auth: AuthService = Depends(get_auth_service),
):
    try:
        actor = auth.verify(token)
        return UserResponse(id=actor.user_id, email=actor.email, roles=list(actor.roles))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/auth/logout", status_code=204)
def logout(
    token: str = Depends(bearer_token),
    auth: AuthService = Depends(get_auth_service),
):
    auth.logout(token)
    return None


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth", "lab": 6}
