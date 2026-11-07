import asyncio
from datetime import UTC, datetime, timedelta
import importlib
import os
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import cli
from app.core.security import verify_password
from app.deployment_targets import resolve_production_database_target
from app.db.base import Base
from app.models import AdminBootstrapEvent, AdminBootstrapState, User
from app.services.admin_bootstrap import (
    AdminBootstrapError,
    bootstrap_first_admin,
    issue_admin_bootstrap_grant,
)

MIGRATION = importlib.import_module(
    "migrations.versions.d129a4c7e601_admin_bootstrap"
)


async def _seed_bootstrap_state(test_session: async_sessionmaker) -> None:
    async with test_session() as session:
        session.add(AdminBootstrapState(id=1))
        await session.commit()


async def _issue(
    test_session: async_sessionmaker,
    *,
    now: datetime | None = None,
) -> str:
    captured: list[str] = []
    async with test_session() as session:
        async with session.begin():
            await issue_admin_bootstrap_grant(
                session,
                actor="synthetic-operator:1000",
                store_secret=captured.append,
                now=now,
            )
    assert len(captured) == 1
    return captured[0]


@pytest.mark.anyio
async def test_bootstrap_creates_new_admin_and_allows_separate_admin_session(
    auth_client,
) -> None:
    client, test_session = auth_client
    await _seed_bootstrap_state(test_session)
    secret = await _issue(test_session)

    async with test_session() as session:
        async with session.begin():
            admin, _ = await bootstrap_first_admin(
                session,
                username="FirstAdmin",
                password="a-synthetic-admin-password",
                secret=secret,
                actor="synthetic-operator:1000",
            )
            admin_id = admin.id

    async with test_session() as session:
        stored_admin = await session.get(User, admin_id)
        state = await session.get(AdminBootstrapState, 1)
        events = (
            await session.scalars(
                select(AdminBootstrapEvent).order_by(AdminBootstrapEvent.event_type)
            )
        ).all()
        assert stored_admin is not None
        assert stored_admin.is_admin is True
        assert stored_admin.password_hash != "a-synthetic-admin-password"
        assert verify_password("a-synthetic-admin-password", stored_admin.password_hash)
        assert state is not None
        assert state.secret_hash is not None
        assert secret not in state.secret_hash
        assert state.consumed_at is not None
        assert state.completed_at is not None
        assert {item.event_type for item in events} == {"grant_issued", "admin_created"}
        assert all(secret not in item.actor for item in events)

    login = await client.post(
        "/api/auth/admin/login",
        json={"username": "FirstAdmin", "password": "a-synthetic-admin-password"},
    )
    admin_session = await client.get("/api/auth/admin/session")
    player_session = await client.get("/api/auth/session")
    assert login.status_code == 200
    assert "rpg_admin_session" in login.headers["set-cookie"]
    assert admin_session.status_code == 200
    assert player_session.status_code == 401


@pytest.mark.anyio
async def test_bootstrap_rejects_existing_admin_without_consuming_grant(auth_client) -> None:
    _, test_session = auth_client
    await _seed_bootstrap_state(test_session)
    secret = await _issue(test_session)
    async with test_session() as session:
        session.add(
            User(
                username="ExistingAdmin",
                username_key="existingadmin",
                email=None,
                password_hash="already-hashed",
                display_name="ExistingAdmin",
                is_admin=True,
                status="active",
            )
        )
        await session.commit()

    async with test_session() as session:
        with pytest.raises(AdminBootstrapError, match="Já existe"):
            async with session.begin():
                await bootstrap_first_admin(
                    session,
                    username="OtherAdmin",
                    password="a-synthetic-admin-password",
                    secret=secret,
                    actor="synthetic-operator:1000",
                )
    async with test_session() as session:
        state = await session.get(AdminBootstrapState, 1)
        assert state is not None
        assert state.consumed_at is None
        assert state.completed_at is None


@pytest.mark.anyio
async def test_bootstrap_rejects_invalid_expired_and_replayed_secrets(auth_client) -> None:
    _, test_session = auth_client
    await _seed_bootstrap_state(test_session)
    fixed_now = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    secret = await _issue(test_session, now=fixed_now)
    attempts = [
        ("", fixed_now),
        ("not-the-token", fixed_now),
        (secret, fixed_now + timedelta(minutes=16)),
    ]

    for candidate, now in attempts:
        async with test_session() as session:
            with pytest.raises(AdminBootstrapError, match="inválida ou expirou") as error:
                async with session.begin():
                    await bootstrap_first_admin(
                        session,
                        username="FirstAdmin",
                        password="a-synthetic-admin-password",
                        secret=candidate,
                        actor="synthetic-operator:1000",
                        now=now,
                    )
            if candidate:
                assert candidate not in str(error.value)

    async with test_session() as session:
        async with session.begin():
            await bootstrap_first_admin(
                session,
                username="FirstAdmin",
                password="a-synthetic-admin-password",
                secret=secret,
                actor="synthetic-operator:1000",
                now=fixed_now + timedelta(minutes=1),
            )
    async with test_session() as session:
        with pytest.raises(AdminBootstrapError, match="concluído"):
            async with session.begin():
                await bootstrap_first_admin(
                    session,
                    username="SecondAdmin",
                    password="another-synthetic-admin-password",
                    secret=secret,
                    actor="synthetic-operator:1000",
                    now=fixed_now + timedelta(minutes=2),
                )


@pytest.mark.anyio
async def test_failed_admin_insert_rolls_back_secret_consumption(auth_client) -> None:
    _, test_session = auth_client
    await _seed_bootstrap_state(test_session)
    secret = await _issue(test_session)

    def fail_before_user_insert(*args) -> None:
        assert len(args) == 3
        raise RuntimeError("synthetic transaction failure")

    event.listen(User, "before_insert", fail_before_user_insert)
    try:
        async with test_session() as session:
            with pytest.raises(RuntimeError, match="synthetic transaction failure"):
                async with session.begin():
                    await bootstrap_first_admin(
                        session,
                        username="FirstAdmin",
                        password="a-synthetic-admin-password",
                        secret=secret,
                        actor="synthetic-operator:1000",
                    )
    finally:
        event.remove(User, "before_insert", fail_before_user_insert)

    async with test_session() as session:
        state = await session.get(AdminBootstrapState, 1)
        assert state is not None
        assert state.consumed_at is None
        assert state.completed_at is None
        assert await session.scalar(select(User.id).where(User.is_admin.is_(True))) is None


@pytest.mark.anyio
async def test_bootstrap_username_conflict_does_not_promote_or_consume(auth_client) -> None:
    _, test_session = auth_client
    await _seed_bootstrap_state(test_session)
    secret = await _issue(test_session)
    async with test_session() as session:
        session.add(
            User(
                username="TakenName",
                username_key="takenname",
                email=None,
                password_hash="player-password-hash",
                display_name="TakenName",
                is_admin=False,
                status="active",
            )
        )
        await session.commit()

    async with test_session() as session:
        with pytest.raises(AdminBootstrapError, match="nenhuma conta foi alterada"):
            async with session.begin():
                await bootstrap_first_admin(
                    session,
                    username="TakenName",
                    password="a-synthetic-admin-password",
                    secret=secret,
                    actor="synthetic-operator:1000",
                )
    async with test_session() as session:
        player = await session.scalar(select(User).where(User.username_key == "takenname"))
        state = await session.get(AdminBootstrapState, 1)
        assert player is not None
        assert player.is_admin is False
        assert player.password_hash == "player-password-hash"
        assert state is not None
        assert state.consumed_at is None


@pytest.mark.anyio
async def test_concurrent_bootstraps_have_only_one_success(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bootstrap-concurrency.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    test_session = async_sessionmaker(engine, expire_on_commit=False)
    await _seed_bootstrap_state(test_session)
    secret = await _issue(test_session)

    async def attempt(username: str) -> bool:
        async with test_session() as session:
            try:
                async with session.begin():
                    await bootstrap_first_admin(
                        session,
                        username=username,
                        password="a-synthetic-admin-password",
                        secret=secret,
                        actor="synthetic-operator:1000",
                    )
                return True
            except AdminBootstrapError:
                return False

    results = await asyncio.gather(attempt("ConcurrentOne"), attempt("ConcurrentTwo"))
    async with test_session() as session:
        admins = (
            await session.scalars(select(User).where(User.is_admin.is_(True)))
        ).all()
        state = await session.get(AdminBootstrapState, 1)
        assert sum(results) == 1
        assert len(admins) == 1
        assert state is not None and state.completed_at is not None
    await engine.dispose()


def test_production_database_target_requires_explicit_nonlocal_identity() -> None:
    environment = {
        "APP_ENVIRONMENT": "production",
        "ADMIN_OPERATION_TARGET": "production",
        "ADMIN_BOOTSTRAP_ENABLED": "true",
        "ADMIN_EXPECTED_DATABASE": "chronicas_prod",
        "ADMIN_EXPECTED_DATABASE_HOST": "db.internal.example",
        "ADMIN_EXPECTED_DATABASE_SCHEMA": "public",
    }
    target = resolve_production_database_target(
        environment,
        database_url="postgresql+asyncpg://db.internal.example/chronicas_prod",
        require_bootstrap_enabled=True,
    )
    assert target.database_name == "chronicas_prod"
    assert target.schema_name == "public"

    bad_targets = [
        ("chronicas_dev", "db.internal.example"),
        ("chronicas_prod", "localhost"),
    ]
    for database, host in bad_targets:
        invalid_environment = {
            **environment,
            "ADMIN_EXPECTED_DATABASE": database,
            "ADMIN_EXPECTED_DATABASE_HOST": host,
        }
        with pytest.raises(RuntimeError):
            resolve_production_database_target(
                invalid_environment,
                database_url=f"postgresql+asyncpg://{host}/{database}",
                require_bootstrap_enabled=True,
            )

    with pytest.raises(RuntimeError, match="explicitly enabled"):
        resolve_production_database_target(
            {key: value for key, value in environment.items() if key != "ADMIN_BOOTSTRAP_ENABLED"},
            database_url="postgresql+asyncpg://db.internal.example/chronicas_prod",
            require_bootstrap_enabled=True,
        )


def test_existing_test_only_cli_refuses_production_environment(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["app.cli", "create-admin"])
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    with pytest.raises(SystemExit, match="test-only"):
        cli.main()
    assert "SyntheticAdmin" not in capsys.readouterr().out


def test_bootstrap_secret_file_is_restricted_and_never_overwritten(tmp_path, monkeypatch) -> None:
    secret_directory = tmp_path / "admin-bootstrap"
    secret_directory.mkdir()
    secret_directory.chmod(0o700)
    monkeypatch.setattr(cli, "_BOOTSTRAP_SECRET_DIRECTORY", secret_directory)
    secret_path = secret_directory / "grant"
    secret = "synthetic-one-time-secret-value-32"

    cli._store_bootstrap_secret(secret_path, secret)
    if os.name == "posix":
        assert secret_path.stat().st_mode & 0o777 == 0o600
    assert cli._read_bootstrap_secret(secret_path) == secret
    with pytest.raises(FileExistsError):
        cli._store_bootstrap_secret(secret_path, "replacement-secret")

    if os.name == "posix":
        secret_path.chmod(0o644)
        with pytest.raises(AdminBootstrapError, match="permissões") as error:
            cli._read_bootstrap_secret(secret_path)
        assert secret not in str(error.value)


def test_bootstrap_migration_upgrade_and_safe_downgrade() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")

    async def run_migration() -> None:
        async with engine.begin() as connection:
            def upgrade(sync_connection) -> None:
                with Operations.context(MigrationContext.configure(sync_connection)):
                    MIGRATION.upgrade()

            await connection.run_sync(upgrade)
        async with engine.connect() as connection:
            state_rows = await connection.exec_driver_sql(
                "SELECT id, secret_hash FROM admin_bootstrap_state"
            )
            assert state_rows.all() == [(1, None)]
        async with engine.begin() as connection:
            def downgrade(sync_connection) -> None:
                with Operations.context(MigrationContext.configure(sync_connection)):
                    MIGRATION.downgrade()

            await connection.run_sync(downgrade)

    asyncio.run(run_migration())
    asyncio.run(engine.dispose())


def test_bootstrap_migration_refuses_downgrade_after_audit_event() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")

    async def run_migration() -> None:
        async with engine.begin() as connection:
            def upgrade(sync_connection) -> None:
                with Operations.context(MigrationContext.configure(sync_connection)):
                    MIGRATION.upgrade()

            await connection.run_sync(upgrade)
        async with engine.begin() as connection:
            await connection.exec_driver_sql(
                """
                INSERT INTO admin_bootstrap_events
                    (id, operation_id, event_type, actor, admin_user_id, target_environment)
                VALUES
                    ('00000000-0000-0000-0000-000000000001',
                     'synthetic-operation', 'grant_issued',
                     'synthetic-operator', NULL, 'production')
                """
            )
        async with engine.begin() as connection:
            def downgrade(sync_connection) -> None:
                with Operations.context(MigrationContext.configure(sync_connection)):
                    MIGRATION.downgrade()

            with pytest.raises(RuntimeError, match="refusing to remove"):
                await connection.run_sync(downgrade)
            tables = await connection.run_sync(
                lambda sync_connection: set(
                    __import__("sqlalchemy").inspect(sync_connection).get_table_names()
                )
            )
            assert "admin_bootstrap_state" in tables
            assert "admin_bootstrap_events" in tables

    asyncio.run(run_migration())
    asyncio.run(engine.dispose())
