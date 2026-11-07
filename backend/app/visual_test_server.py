import argparse
import asyncio
import json
import os

import uvicorn
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.test_environment import IsolatedTestTarget, resolve_visual_server_target


async def _verify_visual_database(
    engine: AsyncEngine,
    target: IsolatedTestTarget,
    expected_tables: set[str],
    legacy_tables: set[str] | None = None,
) -> None:
    async with engine.connect() as connection:
        identity = (
            await connection.execute(
                text(
                    "SELECT current_database(), current_schema(), "
                    "current_setting('search_path')"
                )
            )
        ).one()
        table_names = set(
            (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = :schema_name"
                    ),
                    {"schema_name": target.schema_name},
                )
            ).scalars()
        )
        alembic_table_exists = await connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema_name AND table_name = 'alembic_version')"
            ),
            {"schema_name": target.schema_name},
        )
        alembic_revisions = []
        if alembic_table_exists:
            alembic_revisions = list(
                (
                    await connection.execute(
                        text(
                            f'SELECT version_num FROM "{target.schema_name}".alembic_version'
                        )
                    )
                ).scalars()
            )

    if identity[0] != "cronicas_do_reino_test":
        raise RuntimeError("Visual test server must use cronicas_do_reino_test.")
    if identity[1] != target.schema_name or identity[2] != target.schema_name:
        raise RuntimeError("Visual test server is not isolated to the authorized schema.")
    table_names.discard("alembic_version")
    valid_table_sets = {frozenset(expected_tables)}
    if legacy_tables is not None:
        valid_table_sets.add(frozenset(legacy_tables))
    if frozenset(table_names) not in valid_table_sets:
        raise RuntimeError("Visual test schema does not contain the expected tables.")
    if target.schema_name.startswith("test_asset_h_") and alembic_revisions != [
        "9f3a2b1c4d5e"
    ]:
        raise RuntimeError("Asset visual schema is not at the required Alembic revision.")


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an isolated visual-test API.")
    parser.add_argument("--schema", help="Authorized test_asset_h_* or legacy test_visual_g_* schema.")
    parser.add_argument("--port", type=int, help="Local API port (default: ASSET_VISUAL_PORT or 8000).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    arguments = _arguments(argv)
    target, port, frontend_origin = resolve_visual_server_target(
        os.environ,
        legacy_database_url=os.environ.get("DATABASE_URL"),
        schema_override=arguments.schema,
        port_override=arguments.port,
    )

    os.environ["DATABASE_URL"] = target.database_url.render_as_string(hide_password=False)
    os.environ["FRONTEND_ORIGINS"] = json.dumps([frontend_origin])

    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import app
    from app.db import session as database_session
    from app.db.base import Base
    import app.models as _models  # noqa: F401

    expected_tables = set(Base.metadata.tables)
    asset_tables = {"assets", "asset_entity_associations"}
    legacy_tables = expected_tables - asset_tables
    connect_args = {"server_settings": {"search_path": target.schema_name}}

    async def verify_and_configure() -> AsyncEngine:
        verification_engine = create_async_engine(
            target.database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        try:
            await _verify_visual_database(
                verification_engine,
                target,
                expected_tables,
                legacy_tables if target.schema_name.startswith("test_visual_g_") else None,
            )
        except Exception:
            await verification_engine.dispose()
            raise
        await verification_engine.dispose()
        await database_session.engine.dispose()
        engine = create_async_engine(
            target.database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        database_session.engine = engine
        database_session.SessionLocal = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )
        return engine

    engine = asyncio.run(verify_and_configure())

    async def serve() -> None:
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port))
        try:
            await server.serve()
        finally:
            await engine.dispose()

    asyncio.run(serve())


if __name__ == "__main__":
    main()
