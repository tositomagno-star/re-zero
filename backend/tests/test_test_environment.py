import asyncio
import json
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import cli
import app.test_environment as test_environment
from scripts.secure_asset_preflight import (
    _build_test_database_url,
    _is_local_configured_host,
    _is_local_server_address,
    _listener_processes_are_postgres,
    _safe_database_error_summary,
)
from app.test_environment import (
    configure_migration_context,
    migration_connect_args,
    resolve_admin_test_target,
    resolve_asset_migration_target,
    resolve_visual_server_target,
    validate_test_database_url,
    validate_test_schema,
    verify_migration_connection,
    verify_migration_connection_and_end_transaction,
)
from app.visual_test_server import _verify_visual_database


TEST_URL = "postgresql+asyncpg://test_user:unused@127.0.0.1:5432/cronicas_do_reino_test"
ASSET_SCHEMA = "test_asset_h_0123456789ab"
VISUAL_SCHEMA = "test_visual_g_0123456789ab"


def test_preflight_url_encodes_special_characters_without_changing_target() -> None:
    password = "test@:/?#% secret"
    url = make_url(_build_test_database_url(password))

    assert url.password == password
    assert url.username == "cronicas_local"
    assert url.host == "127.0.0.1"
    assert url.port == 5432
    assert url.database == "cronicas_do_reino_test"


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("::ffff:127.0.0.1", True),
        ("192.168.1.10", False),
        ("::ffff:192.168.1.10", False),
        ("0.0.0.0", False),
        ("::", False),
        (None, False),
        ("not-an-ip", False),
    ],
)
def test_preflight_accepts_only_loopback_postgresql_server_addresses(
    address: str | None,
    expected: bool,
) -> None:
    assert _is_local_server_address(address) is expected


def test_preflight_host_accepts_ip_loopback_and_resolved_localhost_only() -> None:
    def local_resolver(host: str, port: int, *, type: int):
        assert host == "localhost"
        assert port == 5432
        return [
            (None, None, None, None, ("127.0.0.1", port)),
            (None, None, None, None, ("::1", port, 0, 0)),
        ]

    assert _is_local_configured_host("127.0.0.1")
    assert _is_local_configured_host("::1")
    assert _is_local_configured_host("localhost.", resolver=local_resolver)
    assert not _is_local_configured_host("db.internal", resolver=local_resolver)


@pytest.mark.parametrize(
    "addresses",
    [
        [("127.0.0.1", 5432)],
        [("::1", 5432, 0, 0)],
        [("127.0.0.1", 5432), ("192.168.1.5", 5432)],
        [],
    ],
)
def test_preflight_localhost_requires_all_resolutions_to_be_loopback(addresses) -> None:
    def resolver(_host: str, _port: int, *, type: int):
        return [
            (None, None, None, None, address)
            for address in addresses
        ]

    assert _is_local_configured_host("localhost", resolver=resolver) is (
        bool(addresses)
        and all(_is_local_server_address(address[0]) for address in addresses)
    )


def test_preflight_listener_verification_requires_postgres_process() -> None:
    def runner_for(output: str):
        def run(*_args, **_kwargs):
            return SimpleNamespace(stdout=output)

        return run

    assert _listener_processes_are_postgres(
        5432,
        platform="nt",
        run=runner_for(json.dumps(["postgres", "postgres"])),
    )
    assert not _listener_processes_are_postgres(
        5432,
        platform="nt",
        run=runner_for(json.dumps(["ssh"])),
    )
    assert not _listener_processes_are_postgres(
        5432,
        platform="nt",
        run=runner_for("null"),
    )
    assert not _listener_processes_are_postgres(
        5432,
        platform="linux",
        run=runner_for('"postgres"'),
    )
    assert not _listener_processes_are_postgres(
        5432,
        platform="nt",
        run=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, "powershell")
        ),
    )
    assert not _listener_processes_are_postgres(
        5432,
        platform="nt",
        run=runner_for('"postgres; Remove-Item *"'),
    )


@pytest.mark.parametrize(
    ("exception_type", "sqlstate", "expected"),
    [
        ("InvalidPasswordError", "28P01", "authentication rejected"),
        ("InvalidCatalogNameError", "3D000", "database name not found"),
        ("InsufficientPrivilegeError", "42501", "lacks a required database privilege"),
        ("ConnectionResetError", None, "connection was reset or closed"),
    ],
)
def test_preflight_error_summary_classifies_failures_without_raw_messages(
    exception_type: str,
    sqlstate: str | None,
    expected: str,
) -> None:
    driver_error_type = type(exception_type, (Exception,), {})
    original = driver_error_type("password=do-not-print")
    original.sqlstate = sqlstate
    error = Exception("password=do-not-print")
    error.orig = original
    summary = _safe_database_error_summary(error)

    assert expected in summary
    assert "do-not-print" not in summary


def test_asset_migration_requires_explicit_test_url_and_asset_schema() -> None:
    target = resolve_asset_migration_target(
        {"TEST_DATABASE_URL": TEST_URL, "TEST_ASSET_SCHEMA": ASSET_SCHEMA}
    )

    assert target.database_url.database == "cronicas_do_reino_test"
    assert target.schema_name == ASSET_SCHEMA
    with pytest.raises(RuntimeError, match="explicit test database URL"):
        resolve_asset_migration_target({"TEST_ASSET_SCHEMA": ASSET_SCHEMA})
    with pytest.raises(RuntimeError, match="explicit test schema"):
        resolve_asset_migration_target({"TEST_DATABASE_URL": TEST_URL})


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://user:unused@127.0.0.1/cronicas_do_reino_dev",
        "postgresql+asyncpg://user:unused@127.0.0.1/other_database",
        "postgresql+asyncpg://user:unused@example.com/cronicas_do_reino_test",
        "sqlite+aiosqlite:///test.db",
    ],
)
def test_test_database_url_rejects_non_local_or_non_test_targets(url: str) -> None:
    with pytest.raises(RuntimeError):
        validate_test_database_url(url)


def test_asset_schema_requires_exact_safe_identifier_pattern() -> None:
    assert validate_test_schema(ASSET_SCHEMA) == ASSET_SCHEMA
    for schema in (
        VISUAL_SCHEMA,
        "public",
        "test_asset_h_0123456789ab; DROP SCHEMA public",
        'test_asset_h_"unsafe',
        "test_asset_h_0123456789abc",
        "test_asset_h_gggggggggggg",
    ):
        with pytest.raises(RuntimeError):
            validate_test_schema(schema)
    assert validate_test_schema(VISUAL_SCHEMA, allow_visual=True) == VISUAL_SCHEMA


def test_migration_search_path_and_version_table_schema_are_explicit() -> None:
    assert migration_connect_args(ASSET_SCHEMA) == {
        "server_settings": {"search_path": ASSET_SCHEMA}
    }

    captured: dict[str, object] = {}
    context = SimpleNamespace(
        configure=lambda **kwargs: captured.update(kwargs),
    )
    metadata = object()
    connection = object()
    configure_migration_context(context, connection, ASSET_SCHEMA, metadata)

    assert captured == {
        "connection": connection,
        "target_metadata": metadata,
        "compare_type": True,
        "version_table_schema": ASSET_SCHEMA,
    }


class _FakeConnection:
    def __init__(self, database: str, schema: str, search_path: str) -> None:
        self.row = (database, schema, search_path)

    def execute(self, _statement):
        return SimpleNamespace(one=lambda: self.row)


def test_migration_connection_fails_closed_outside_authorized_target() -> None:
    verify_migration_connection(
        _FakeConnection("cronicas_do_reino_test", ASSET_SCHEMA, ASSET_SCHEMA),
        ASSET_SCHEMA,
    )
    with pytest.raises(RuntimeError, match="authorized test database"):
        verify_migration_connection(
            _FakeConnection("cronicas_do_reino_dev", ASSET_SCHEMA, ASSET_SCHEMA),
            ASSET_SCHEMA,
        )
    with pytest.raises(RuntimeError, match="authorized schema"):
        verify_migration_connection(
            _FakeConnection("cronicas_do_reino_test", "public", "public"),
            ASSET_SCHEMA,
        )


def test_migration_validation_ends_guard_transaction_before_alembic_owns_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_guard(connection, _schema_name: str) -> None:
        connection.execute(text("SELECT 1")).one()

    monkeypatch.setattr(test_environment, "verify_migration_connection", run_guard)

    with create_engine("sqlite://").connect() as connection:
        verify_migration_connection_and_end_transaction(connection, ASSET_SCHEMA)
        assert not connection.in_transaction()

        migration_context = MigrationContext.configure(connection=connection)
        migration_context.impl.transactional_ddl = True
        with migration_context.begin_transaction():
            assert connection.in_transaction()
        assert not connection.in_transaction()


def test_migration_validation_failure_is_not_committed_or_suppressed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_connection(connection, _schema_name: str) -> None:
        connection.execute(text("SELECT 1")).one()
        raise RuntimeError("Migration connection is not the authorized target.")

    monkeypatch.setattr(test_environment, "verify_migration_connection", reject_connection)

    with create_engine("sqlite://").connect() as connection:
        with pytest.raises(RuntimeError, match="authorized target"):
            verify_migration_connection_and_end_transaction(connection, ASSET_SCHEMA)
        assert connection.in_transaction()


def test_admin_cli_resolves_asset_and_legacy_visual_targets_safely() -> None:
    asset_target = resolve_admin_test_target(
        {"TEST_DATABASE_URL": TEST_URL, "TEST_ASSET_SCHEMA": ASSET_SCHEMA},
        legacy_database_url=None,
    )
    assert asset_target is not None
    assert asset_target.schema_name == ASSET_SCHEMA

    visual_target = resolve_admin_test_target(
        {"DATABASE_URL": TEST_URL, "VISUAL_TEST_SCHEMA": VISUAL_SCHEMA},
        legacy_database_url=TEST_URL,
    )
    assert visual_target is not None
    assert visual_target.schema_name == VISUAL_SCHEMA

    with pytest.raises(RuntimeError):
        resolve_admin_test_target(
            {
                "TEST_DATABASE_URL": TEST_URL,
                "TEST_ASSET_SCHEMA": ASSET_SCHEMA,
                "VISUAL_TEST_SCHEMA": VISUAL_SCHEMA,
            },
            legacy_database_url=None,
        )
    with pytest.raises(RuntimeError):
        resolve_admin_test_target(
            {"DATABASE_URL": TEST_URL, "VISUAL_TEST_SCHEMA": "public"},
            legacy_database_url=TEST_URL,
        )
    with pytest.raises(RuntimeError):
        resolve_admin_test_target(
            {
                "DATABASE_URL": "postgresql+asyncpg://user:unused@127.0.0.1/cronicas_do_reino_dev",
                "VISUAL_TEST_SCHEMA": VISUAL_SCHEMA,
            },
            legacy_database_url=None,
        )
    assert resolve_admin_test_target({}, legacy_database_url=None) is None


def test_admin_cli_never_promotes_an_existing_account(monkeypatch: pytest.MonkeyPatch) -> None:
    existing_id = uuid4()
    session_state = {"commits": 0, "added": False}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, _statement):
            return SimpleNamespace(
                one=lambda: (
                    "cronicas_do_reino_test",
                    "test_user",
                    ASSET_SCHEMA,
                    ASSET_SCHEMA,
                    "127.0.0.1",
                )
            )

        async def scalar(self, _statement):
            return existing_id

        def add(self, _user):
            session_state["added"] = True

        async def commit(self):
            session_state["commits"] += 1

    class FakeEngine:
        async def dispose(self):
            return None

    monkeypatch.setattr(cli, "create_async_engine", lambda *_args, **_kwargs: FakeEngine())
    monkeypatch.setattr(cli, "async_sessionmaker", lambda *_args, **_kwargs: lambda: FakeSession())

    target = resolve_asset_migration_target(
        {"TEST_DATABASE_URL": TEST_URL, "TEST_ASSET_SCHEMA": ASSET_SCHEMA}
    )
    with pytest.raises(ValueError, match="already exists"):
        asyncio.run(cli._create_admin("SyntheticAdmin", "not-a-real-password", target))
    assert session_state == {"commits": 0, "added": False}


def test_admin_cli_rejects_mismatched_runtime_target_before_writing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_state = {"account_lookups": 0, "commits": 0, "added": False}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, _statement):
            return SimpleNamespace(
                one=lambda: (
                    "cronicas_do_reino_dev",
                    "cronicas_local",
                    ASSET_SCHEMA,
                    ASSET_SCHEMA,
                    "127.0.0.1",
                )
            )

        async def scalar(self, _statement):
            session_state["account_lookups"] += 1
            return None

        def add(self, _user):
            session_state["added"] = True

        async def commit(self):
            session_state["commits"] += 1

    class FakeEngine:
        async def dispose(self):
            return None

    monkeypatch.setattr(cli, "create_async_engine", lambda *_args, **_kwargs: FakeEngine())
    monkeypatch.setattr(cli, "async_sessionmaker", lambda *_args, **_kwargs: lambda: FakeSession())

    target = resolve_asset_migration_target(
        {"TEST_DATABASE_URL": TEST_URL, "TEST_ASSET_SCHEMA": ASSET_SCHEMA}
    )
    with pytest.raises(RuntimeError, match="authorized local test target"):
        asyncio.run(cli._create_admin("SyntheticAdmin", "not-a-real-password", target))
    assert session_state == {"account_lookups": 0, "commits": 0, "added": False}


def test_admin_cli_password_prompts_do_not_echo_password(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "SyntheticAdmin")
    secrets = iter(("synthetic-password-value", "synthetic-password-value"))
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(secrets))

    username, password = cli._read_admin_credentials()

    assert username == "SyntheticAdmin"
    assert password == "synthetic-password-value"
    assert "synthetic-password-value" not in capsys.readouterr().out


def test_visual_server_requires_explicit_test_database_and_supports_isolated_ports() -> None:
    target, port, origin = resolve_visual_server_target(
        {"TEST_DATABASE_URL": TEST_URL, "TEST_ASSET_SCHEMA": ASSET_SCHEMA},
        legacy_database_url=None,
        schema_override=None,
        port_override=8001,
    )
    assert target.database_url.database == "cronicas_do_reino_test"
    assert target.schema_name == ASSET_SCHEMA
    assert port == 8001
    assert origin == "http://127.0.0.1:8081"

    old_target, old_port, old_origin = resolve_visual_server_target(
        {"DATABASE_URL": TEST_URL, "VISUAL_TEST_SCHEMA": VISUAL_SCHEMA},
        legacy_database_url=None,
        schema_override=None,
        port_override=None,
    )
    assert old_target.schema_name == VISUAL_SCHEMA
    assert old_port == 8000
    assert old_origin == "http://127.0.0.1:8080"

    with pytest.raises(RuntimeError):
        resolve_visual_server_target(
            {"DATABASE_URL": "postgresql+asyncpg://u:p@localhost/cronicas_do_reino_dev",
             "VISUAL_TEST_SCHEMA": VISUAL_SCHEMA},
            legacy_database_url=None,
            schema_override=None,
            port_override=None,
        )
    with pytest.raises(RuntimeError, match="explicit test database URL"):
        resolve_visual_server_target(
            {"TEST_ASSET_SCHEMA": ASSET_SCHEMA},
            legacy_database_url=None,
            schema_override=None,
            port_override=8001,
        )
    with pytest.raises(RuntimeError):
        resolve_visual_server_target(
            {"TEST_DATABASE_URL": TEST_URL, "TEST_ASSET_SCHEMA": ASSET_SCHEMA},
            legacy_database_url=None,
            schema_override=None,
            port_override=80,
        )


class _FakeResult:
    def __init__(self, values):
        self.values = values

    def one(self):
        return self.values

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self.values)


class _FakeAsyncConnection:
    def __init__(self, identity, tables, revisions=()):
        self.identity = identity
        self.tables = tables
        self.revisions = revisions

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, statement, _parameters=None):
        sql = str(statement)
        if "current_database()" in sql:
            return _FakeResult(self.identity)
        if "alembic_version" in sql:
            return _FakeResult(self.revisions)
        return _FakeResult(self.tables)

    async def scalar(self, statement, _parameters=None):
        if "information_schema.tables" in str(statement):
            return bool(self.revisions)
        return None


class _FakeAsyncEngine:
    def __init__(self, identity, tables, revisions=()):
        self.connection = _FakeAsyncConnection(identity, tables, revisions)

    def connect(self):
        return self.connection


def test_visual_server_checks_exact_schema_and_preserves_legacy_table_shape() -> None:
    target = resolve_asset_migration_target(
        {"TEST_DATABASE_URL": TEST_URL, "TEST_ASSET_SCHEMA": ASSET_SCHEMA}
    )
    expected_tables = {"assets", "asset_entity_associations", "users"}
    legacy_tables = {"users"}

    asyncio.run(
        _verify_visual_database(
            _FakeAsyncEngine(
                ("cronicas_do_reino_test", ASSET_SCHEMA, ASSET_SCHEMA),
                [*expected_tables, "alembic_version"],
                ["9f3a2b1c4d5e"],
            ),
            target,
            expected_tables,
        )
    )
    with pytest.raises(RuntimeError, match="isolated"):
        asyncio.run(
            _verify_visual_database(
                _FakeAsyncEngine(
                    ("cronicas_do_reino_test", "public", "public"),
                    list(expected_tables),
                    ["9f3a2b1c4d5e"],
                ),
                target,
                expected_tables,
            )
        )

    legacy_target = resolve_visual_server_target(
        {"DATABASE_URL": TEST_URL, "VISUAL_TEST_SCHEMA": VISUAL_SCHEMA},
        legacy_database_url=None,
        schema_override=None,
        port_override=None,
    )[0]
    asyncio.run(
        _verify_visual_database(
            _FakeAsyncEngine(
                ("cronicas_do_reino_test", VISUAL_SCHEMA, VISUAL_SCHEMA),
                [*legacy_tables, "alembic_version"],
            ),
            legacy_target,
            expected_tables,
            legacy_tables,
        )
    )
