from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_allows_insecure_cookie_for_local_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("COOKIE_SECURE", "false")

    settings = Settings(_env_file=None)

    assert settings.cookie_secure is False


def test_production_requires_and_accepts_secure_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("COOKIE_SECURE", "true")

    settings = Settings(_env_file=None)

    assert settings.cookie_secure is True


def test_production_rejects_insecure_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("COOKIE_SECURE", "false")

    with pytest.raises(ValidationError, match="COOKIE_SECURE=false"):
        Settings(_env_file=None)


def test_missing_environment_requires_secure_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)
    monkeypatch.setenv("COOKIE_SECURE", "false")

    with pytest.raises(ValidationError, match="APP_ENVIRONMENT=development"):
        Settings(_env_file=None)

    monkeypatch.setenv("COOKIE_SECURE", "true")
    settings = Settings(_env_file=None)
    assert settings.app_environment is None


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setenv("COOKIE_SECURE", "true")

    with pytest.raises(ValidationError, match="Input should be 'development' or 'production'"):
        Settings(_env_file=None)


def test_asset_storage_and_upload_limit_are_configurable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("ASSET_STORAGE_PATH", str(tmp_path / "persistent-assets"))
    monkeypatch.setenv("ASSET_MAX_UPLOAD_BYTES", "1048576")

    settings = Settings(_env_file=None)

    assert settings.asset_storage_path == tmp_path / "persistent-assets"
    assert settings.asset_max_upload_bytes == 1024 * 1024


def test_asset_upload_limit_cannot_exceed_database_constraint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("ASSET_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024 + 1))

    with pytest.raises(ValidationError, match="asset_max_upload_bytes"):
        Settings(_env_file=None)
