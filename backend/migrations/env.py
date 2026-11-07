import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.deployment_targets import (
    ProductionDatabaseTarget,
    resolve_production_database_target,
)
from app.test_environment import (
    IsolatedTestTarget,
    configure_migration_context,
    resolve_asset_migration_target,
    verify_migration_connection_and_end_transaction,
    verify_production_migration_connection,
)
import app.models  # noqa: F401
_ = app.models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    raise RuntimeError(
        "Offline migrations are disabled; use an explicitly isolated test schema."
    )


def do_run_migrations(
    connection: Connection,
    target: IsolatedTestTarget | ProductionDatabaseTarget,
) -> None:
    if isinstance(target, ProductionDatabaseTarget):
        verify_production_migration_connection(
            connection,
            database_name=target.database_name,
            schema_name=target.schema_name,
        )
        if connection.in_transaction():
            raise RuntimeError("Migration connection already has an external transaction.")
        connection.commit()
    else:
        verify_migration_connection_and_end_transaction(connection, target.schema_name)
    configure_migration_context(
        context,
        connection,
        target.schema_name,
        target_metadata,
        allow_production_schema=isinstance(target, ProductionDatabaseTarget),
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    if os.environ.get("ADMIN_OPERATION_TARGET") == "production":
        target = resolve_production_database_target(
            os.environ,
            database_url=os.environ.get("DATABASE_URL"),
            require_migrations_enabled=True,
        )
    else:
        target = resolve_asset_migration_target(os.environ)
    connectable = create_async_engine(
        target.database_url,
        connect_args={
            "server_settings": {"search_path": target.schema_name},
        },
        poolclass=pool.NullPool,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations, target)
    finally:
        await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
