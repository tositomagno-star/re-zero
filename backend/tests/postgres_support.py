from collections.abc import Iterable, Mapping
from ipaddress import ip_interface

from sqlalchemy.sql.compiler import IdentifierPreparer

from app.test_environment import IsolatedTestTarget, resolve_asset_migration_target


POSTGRES_TEST_DATABASE = "cronicas_do_reino_test"
POSTGRES_TEST_ROLE = "cronicas_local"
POSTGRES_TEST_SCHEMA = "test_asset_h_7e4c91a2d603"
POSTGRES_TEST_REVISION = "c83d42e7a901"
ALEMBIC_VERSION_TABLE = "alembic_version"


def resolve_postgres_test_target(
    environment: Mapping[str, str],
) -> IsolatedTestTarget:
    target = resolve_asset_migration_target(environment)
    if target.database_url.database != POSTGRES_TEST_DATABASE:
        raise RuntimeError("PostgreSQL tests must use the dedicated test database.")
    if target.database_url.username != POSTGRES_TEST_ROLE:
        raise RuntimeError("PostgreSQL tests must use the dedicated test role.")
    if target.schema_name != POSTGRES_TEST_SCHEMA:
        raise RuntimeError("PostgreSQL tests must use the isolated test schema.")
    return target


def validate_postgres_test_catalog(
    *,
    database_name: str,
    role_name: str,
    server_address: str | None,
    current_schema: str | None,
    search_path: str,
    installed_revision: str | None,
    relation_names: Iterable[str],
    expected_table_names: Iterable[str],
) -> None:
    if database_name != POSTGRES_TEST_DATABASE:
        raise RuntimeError(
            "PostgreSQL test connection is not using the dedicated database."
        )
    if role_name != POSTGRES_TEST_ROLE:
        raise RuntimeError(
            "PostgreSQL test connection is not using the dedicated role."
        )
    if server_address is None or not ip_interface(server_address).ip.is_loopback:
        raise RuntimeError(
            "PostgreSQL test connection is not using a loopback server."
        )
    if current_schema != POSTGRES_TEST_SCHEMA:
        raise RuntimeError(
            "PostgreSQL test connection is not using the isolated schema."
        )
    if search_path != POSTGRES_TEST_SCHEMA:
        raise RuntimeError(
            "PostgreSQL test search_path is not restricted to the isolated schema."
        )
    if installed_revision != POSTGRES_TEST_REVISION:
        raise RuntimeError(
            "PostgreSQL test schema is not at the expected migration revision."
        )

    relations = set(relation_names)
    expected_tables = set(expected_table_names)
    expected_relations = expected_tables | {ALEMBIC_VERSION_TABLE}
    if relations != expected_relations:
        unexpected = sorted(relations - expected_relations)
        missing = sorted(expected_relations - relations)
        problems = []
        if missing:
            problems.append("missing: " + ", ".join(missing))
        if unexpected:
            problems.append("unexpected: " + ", ".join(unexpected))
        raise RuntimeError(
            "PostgreSQL test schema relations do not match the migrated application "
            "schema (" + "; ".join(problems) + ")."
        )


def build_postgres_cleanup_statement(
    table_names: Iterable[str],
    identifier_preparer: IdentifierPreparer,
) -> str:
    names = tuple(sorted(set(table_names)))
    if not names:
        raise ValueError("At least one application table is required for cleanup.")
    if ALEMBIC_VERSION_TABLE in names:
        raise ValueError("Cleanup must not include Alembic's version table.")
    qualified_names = ", ".join(
        f"{identifier_preparer.quote_schema(POSTGRES_TEST_SCHEMA)}."
        f"{identifier_preparer.quote(name)}"
        for name in names
    )
    return f"TRUNCATE TABLE {qualified_names}"
