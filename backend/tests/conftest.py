from collections.abc import AsyncIterator
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.test_environment import migration_connect_args
from app.main import app
from tests.postgres_support import (
    build_postgres_cleanup_statement,
    resolve_postgres_test_target,
    validate_postgres_test_catalog,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def auth_client(
    request: pytest.FixtureRequest,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    requires_postgres = request.node.get_closest_marker("postgres") is not None
    test_database_url = os.environ.get("TEST_DATABASE_URL") if requires_postgres else None
    if requires_postgres and test_database_url is None:
        pytest.skip(
            "PostgreSQL integration test not run: set TEST_DATABASE_URL to the local "
            "cronicas_do_reino_test database."
        )

    postgres_target = None
    if test_database_url is not None:
        postgres_target = resolve_postgres_test_target(os.environ)
        application_url = make_url(get_settings().database_url)
        if application_url.database == postgres_target.database_url.database:
            raise ValueError(
                "DATABASE_URL and TEST_DATABASE_URL must target different databases."
            )
        engine = create_async_engine(
            postgres_target.database_url,
            connect_args=migration_connect_args(postgres_target.schema_name),
            poolclass=NullPool,
        )
    else:
        engine = create_async_engine("sqlite+aiosqlite://")

    postgres_cleanup_ready = False

    async def verify_postgres_target(connection: AsyncConnection) -> None:
        if postgres_target is None:
            return
        identity = (
            await connection.execute(
                text(
                    """
                    SELECT current_database(),
                           current_user,
                           inet_server_addr()::text,
                           current_schema(),
                           current_setting('search_path'),
                           (
                               SELECT version_num
                               FROM test_asset_h_7e4c91a2d603.alembic_version
                           )
                    """
                )
            )
        ).one()
        relation_names = (
            await connection.execute(
                text(
                    """
                    SELECT c.relname
                    FROM pg_catalog.pg_class AS c
                    JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                    WHERE n.nspname = :schema_name
                      AND c.relkind IN ('r', 'p')
                    """
                ),
                {"schema_name": postgres_target.schema_name},
            )
        ).scalars()
        validate_postgres_test_catalog(
            database_name=identity[0],
            role_name=identity[1],
            server_address=identity[2],
            current_schema=identity[3],
            search_path=identity[4],
            installed_revision=identity[5],
            relation_names=relation_names,
            expected_table_names=Base.metadata.tables,
        )

    async def clear_postgres_test_data() -> None:
        if postgres_target is None:
            return
        statement = build_postgres_cleanup_statement(
            Base.metadata.tables,
            engine.sync_engine.dialect.identifier_preparer,
        )
        async with engine.begin() as connection:
            await verify_postgres_target(connection)
            await connection.execute(text(statement))

    try:
        if postgres_target is not None:
            async with engine.connect() as connection:
                await verify_postgres_target(connection)
            await clear_postgres_test_data()
            postgres_cleanup_ready = True
        else:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        test_session = async_sessionmaker(engine, expire_on_commit=False)

        async def override_get_db():
            async with test_session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client, test_session
    finally:
        app.dependency_overrides.clear()
        try:
            if postgres_cleanup_ready:
                await clear_postgres_test_data()
        finally:
            await engine.dispose()
