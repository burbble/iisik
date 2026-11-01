import pytest

pytest.importorskip("strawberry")

from app.bootstrap import get_container
from app.gateway.clients.factory import create_grpc_clients
from app.gateway.facade import ApplicationFacade
from app.gateway.schema import schema
from app.scripts.seed import USER_ID, clear_and_seed
from app.shared.security import Actor


def setup_function():
    clear_and_seed()
    get_container.cache_clear()


def context(actor):
    return {"facade": ApplicationFacade(create_grpc_clients()), "actor": actor}


def test_me_returns_verified_user_context():
    actor = Actor(USER_ID, "analyst@example.local", ("ANALYST",), "session")
    result = schema.execute_sync(
        "{ me { id email roles } }", context_value=context(actor)
    )
    assert result.errors is None
    assert result.data["me"]["id"] == USER_ID
    assert "ANALYST" in result.data["me"]["roles"]


def test_protected_query_without_actor_returns_error():
    result = schema.execute_sync(
        "{ products { id code } }", context_value=context(None)
    )
    assert result.errors
    assert "Authentication required" in str(result.errors[0])
