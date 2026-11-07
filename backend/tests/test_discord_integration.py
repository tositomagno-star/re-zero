from app.api.discord import _read_state, _state_cookie
from fastapi import HTTPException
from app.core.config import get_settings


def test_discord_oauth_state_is_bound_to_user(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "app_secret_key", "test-secret")
    state = _state_cookie("user-1")
    _read_state(state, "user-1")
    try:
        _read_state(state, "user-2")
    except HTTPException as error:
        assert error.status_code == 400
    else:
        raise AssertionError("OAuth state accepted for a different user")
