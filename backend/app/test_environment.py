from dataclasses import dataclass
from collections.abc import Mapping
import re

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ASSET_SCHEMA_PATTERN = re.compile(r"test_asset_h_[0-9a-f]{12}\Z")
_VISUAL_SCHEMA_PATTERN = re.compile(r"test_visual_g_[0-9a-f]{12}\Z")
_PRODUCTION_SCHEMA_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}\Z")


@dataclass(frozen=True)
class IsolatedTestTarget:
    database_url: URL
    schema_name: str


def validate_test_database_url(raw_url: str | None) -> URL:
    if not raw_url:
        raise RuntimeError("An explicit test database URL is required.")
    try:
        database_url = make_url(raw_url)
    except Exception as error:
        raise RuntimeError("The test database URL is invalid.") from error
    if database_url.drivername != "postgresql+asyncpg":
        raise RuntimeError("The test database URL must use PostgreSQL with asyncpg.")
    if database_url.database != "cronicas_do_reino_test":
        raise RuntimeError("The database must be cronicas_do_reino_test.")
    if database_url.host not in _LOCAL_HOSTS:
        raise RuntimeError("The test database must be hosted locally.")
    return database_url


def validate_test_schema(schema_name: str | None, *, allow_visual: bool = False) -> str:
    if schema_name is None:
        raise RuntimeError("An explicit test schema is required.")
    patterns = [_ASSET_SCHEMA_PATTERN]
    if allow_visual:
        patterns.append(_VISUAL_SCHEMA_PATTERN)
    if not any(pattern.fullmatch(schema_name) for pattern in patterns):
        raise RuntimeError("The test schema name is invalid or not authorized.")
    return schema_name


def resolve_asset_migration_target(
    environment: Mapping[str, str],
) -> IsolatedTestTarget:
    database_url = validate_test_database_url(environment.get("TEST_DATABASE_URL"))
    schema_name = validate_test_schema(environment.get("TEST_ASSET_SCHEMA"))
    return IsolatedTestTarget(database_url=database_url, schema_name=schema_name)


def resolve_admin_test_target(
    environment: Mapping[str, str],
    *,
    legacy_database_url: str | None,
) -> IsolatedTestTarget | None:
    asset_schema = environment.get("TEST_ASSET_SCHEMA")
    visual_schema = environment.get("VISUAL_TEST_SCHEMA")
    if asset_schema and visual_schema:
        raise RuntimeError("Choose exactly one authorized test schema.")
    if asset_schema:
        database_url = validate_test_database_url(environment.get("TEST_DATABASE_URL"))
        schema_name = validate_test_schema(asset_schema)
        return IsolatedTestTarget(database_url=database_url, schema_name=schema_name)
    if visual_schema:
        database_url = validate_test_database_url(
            environment.get("TEST_DATABASE_URL") or legacy_database_url
        )
        schema_name = validate_test_schema(visual_schema, allow_visual=True)
        return IsolatedTestTarget(database_url=database_url, schema_name=schema_name)
    return None


def resolve_visual_server_target(
    environment: Mapping[str, str],
    *,
    legacy_database_url: str | None,
    schema_override: str | None,
    port_override: int | None,
) -> tuple[IsolatedTestTarget, int, str]:
    schema_name = schema_override or environment.get("TEST_ASSET_SCHEMA") or environment.get(
        "VISUAL_TEST_SCHEMA"
    )
    schema_name = validate_test_schema(schema_name, allow_visual=True)
    if schema_name.startswith("test_asset_h_"):
        raw_url = environment.get("TEST_DATABASE_URL")
    else:
        raw_url = environment.get("TEST_DATABASE_URL") or environment.get(
            "DATABASE_URL"
        ) or legacy_database_url
    database_url = validate_test_database_url(raw_url)

    raw_port = port_override
    if raw_port is None:
        configured_port = environment.get("ASSET_VISUAL_PORT")
        try:
            raw_port = int(configured_port) if configured_port is not None else 8000
        except ValueError as error:
            raise RuntimeError("The visual API port must be an integer.") from error
    if not 1024 <= raw_port <= 65535:
        raise RuntimeError("The visual API port must be between 1024 and 65535.")

    frontend_port = raw_port + 80
    if frontend_port > 65535:
        raise RuntimeError("The matching frontend port is outside the valid range.")
    frontend_origin = f"http://127.0.0.1:{frontend_port}"
    return (
        IsolatedTestTarget(database_url=database_url, schema_name=schema_name),
        raw_port,
        frontend_origin,
    )


def migration_connect_args(schema_name: str) -> dict[str, dict[str, str]]:
    schema_name = validate_test_schema(schema_name)
    return {"server_settings": {"search_path": schema_name}}


def configure_migration_context(
    context,
    connection,
    schema_name: str,
    target_metadata,
    *,
    allow_production_schema: bool = False,
) -> None:
    if allow_production_schema:
        if not _PRODUCTION_SCHEMA_PATTERN.fullmatch(schema_name):
            raise RuntimeError("The production migration schema name is invalid.")
    else:
        schema_name = validate_test_schema(schema_name)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        version_table_schema=schema_name,
    )


def verify_migration_connection(connection, schema_name: str) -> None:
    schema_name = validate_test_schema(schema_name)
    row = connection.execute(
        text(
            "SELECT current_database(), current_schema(), current_setting('search_path')"
        )
    ).one()
    if row[0] != "cronicas_do_reino_test":
        raise RuntimeError("Migration connection is not the authorized test database.")
    if row[1] != schema_name:
        raise RuntimeError("Migration connection is not using the authorized schema.")
    if row[2] != schema_name:
        raise RuntimeError("Migration search_path is not restricted to the authorized schema.")


def verify_production_migration_connection(
    connection,
    *,
    database_name: str,
    schema_name: str,
) -> None:
    row = connection.execute(
        text(
            "SELECT current_database(), current_schema(), current_setting('search_path')"
        )
    ).one()
    if row[0] != database_name or row[1] != schema_name or row[2] != schema_name:
        raise RuntimeError(
            "Migration connection does not match the explicitly authorized production target."
        )


def verify_migration_connection_and_end_transaction(
    connection,
    schema_name: str,
) -> None:
    if connection.in_transaction():
        raise RuntimeError("Migration connection already has an external transaction.")
    verify_migration_connection(connection, schema_name)
    connection.commit()
