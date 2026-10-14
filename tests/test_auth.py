import pytest

from app.bootstrap import get_container
from app.scripts.seed import DEMO_PASSWORD, USER_ID, clear_and_seed
from app.services.auth.service import AuthService
from app.services.auth.sessions import InMemorySessionStore
from app.services.auth.tokens import JWTManager
from app.shared.errors import AuthenticationError, ConflictError


def setup_function():
    clear_and_seed()
    get_container.cache_clear()


def auth_fixture():
    sessions = InMemorySessionStore()
    service = AuthService(
        sessions=sessions,
        tokens=JWTManager("test-secret-that-is-long-enough-1234567890", ttl_seconds=3600),
    )
    return service, sessions


def test_login_issues_jwt_and_creates_active_session():
    service, sessions = auth_fixture()
    result = service.login("analyst@example.local", DEMO_PASSWORD)
    assert result.actor.user_id == USER_ID
    assert "ANALYST" in result.actor.roles
    assert result.access_token.count(".") == 2
    assert sessions.get(result.actor.session_id) is not None


def test_invalid_password_is_rejected():
    service, _ = auth_fixture()
    with pytest.raises(AuthenticationError):
        service.login("analyst@example.local", "wrong-password")


def test_valid_jwt_without_session_is_rejected():
    service, sessions = auth_fixture()
    result = service.login("analyst@example.local", DEMO_PASSWORD)
    sessions.delete(result.actor.session_id)
    with pytest.raises(AuthenticationError):
        service.verify(result.access_token)


def test_logout_invalidates_session():
    service, _ = auth_fixture()
    result = service.login("analyst@example.local", DEMO_PASSWORD)
    service.logout(result.access_token)
    with pytest.raises(AuthenticationError):
        service.verify(result.access_token)


def test_registration_hashes_password_and_prevents_duplicate_email():
    service, _ = auth_fixture()
    actor = service.register("new.user@example.local", "StrongPass123!")
    assert actor.email == "new.user@example.local"
    login = service.login("new.user@example.local", "StrongPass123!")
    assert login.actor.user_id == actor.user_id
    with pytest.raises(ConflictError):
        service.register("new.user@example.local", "StrongPass123!")
