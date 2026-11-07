import pytest
from sqlalchemy.dialects import postgresql

from tests.postgres_support import (
    POSTGRES_TEST_DATABASE,
    POSTGRES_TEST_REVISION,
    POSTGRES_TEST_ROLE,
    POSTGRES_TEST_SCHEMA,
    build_postgres_cleanup_statement,
    resolve_postgres_test_target,
    validate_postgres_test_catalog,
)


TEST_URL = "postgresql+asyncpg://cronicas_local@127.0.0.1:5432/cronicas_do_reino_test"


def test_postgres_test_target_requires_exact_role_and_schema() -> None:
    target = resolve_postgres_test_target(
        {
            "TEST_DATABASE_URL": TEST_URL,
            "TEST_ASSET_SCHEMA": POSTGRES_TEST_SCHEMA,
        }
    )

    assert target.database_url.database == POSTGRES_TEST_DATABASE
    assert target.database_url.username == POSTGRES_TEST_ROLE
    assert target.schema_name == POSTGRES_TEST_SCHEMA

    with pytest.raises(RuntimeError, match="isolated test schema"):
        resolve_postgres_test_target(
            {
                "TEST_DATABASE_URL": TEST_URL,
                "TEST_ASSET_SCHEMA": "test_asset_h_0123456789ab",
            }
        )


def test_postgres_catalog_validation_requires_isolated_revision_and_tables() -> None:
    validate_postgres_test_catalog(
        database_name=POSTGRES_TEST_DATABASE,
        role_name=POSTGRES_TEST_ROLE,
        server_address="127.0.0.1",
        current_schema=POSTGRES_TEST_SCHEMA,
        search_path=POSTGRES_TEST_SCHEMA,
        installed_revision=POSTGRES_TEST_REVISION,
        relation_names={"users", "alembic_version"},
        expected_table_names={"users"},
    )

    unsafe_targets = [
        {
            "database_name": "cronicas_do_reino_dev",
            "role_name": POSTGRES_TEST_ROLE,
            "server_address": "127.0.0.1",
            "current_schema": POSTGRES_TEST_SCHEMA,
            "search_path": POSTGRES_TEST_SCHEMA,
            "installed_revision": POSTGRES_TEST_REVISION,
        },
        {
            "database_name": POSTGRES_TEST_DATABASE,
            "role_name": POSTGRES_TEST_ROLE,
            "server_address": "127.0.0.1",
            "current_schema": "public",
            "search_path": "public",
            "installed_revision": POSTGRES_TEST_REVISION,
        },
        {
            "database_name": POSTGRES_TEST_DATABASE,
            "role_name": "cronicas_dev_agent",
            "server_address": "127.0.0.1",
            "current_schema": POSTGRES_TEST_SCHEMA,
            "search_path": POSTGRES_TEST_SCHEMA,
            "installed_revision": POSTGRES_TEST_REVISION,
        },
        {
            "database_name": POSTGRES_TEST_DATABASE,
            "role_name": POSTGRES_TEST_ROLE,
            "server_address": "127.0.0.1",
            "current_schema": POSTGRES_TEST_SCHEMA,
            "search_path": f"{POSTGRES_TEST_SCHEMA}, public",
            "installed_revision": POSTGRES_TEST_REVISION,
        },
    ]

    for target in unsafe_targets:
        with pytest.raises(RuntimeError):
            validate_postgres_test_catalog(
                **target,
                relation_names={"users", "alembic_version"},
                expected_table_names={"users"},
            )

    with pytest.raises(RuntimeError, match="missing: users"):
        validate_postgres_test_catalog(
            database_name=POSTGRES_TEST_DATABASE,
            role_name=POSTGRES_TEST_ROLE,
            server_address="127.0.0.1",
            current_schema=POSTGRES_TEST_SCHEMA,
            search_path=POSTGRES_TEST_SCHEMA,
            installed_revision=POSTGRES_TEST_REVISION,
            relation_names={"alembic_version"},
            expected_table_names={"users"},
        )

    with pytest.raises(RuntimeError, match="loopback"):
        validate_postgres_test_catalog(
            database_name=POSTGRES_TEST_DATABASE,
            role_name=POSTGRES_TEST_ROLE,
            server_address="192.0.2.1",
            current_schema=POSTGRES_TEST_SCHEMA,
            search_path=POSTGRES_TEST_SCHEMA,
            installed_revision=POSTGRES_TEST_REVISION,
            relation_names={"users", "alembic_version"},
            expected_table_names={"users"},
        )


def test_postgres_cleanup_sql_qualifies_only_application_tables() -> None:
    preparer = postgresql.dialect().identifier_preparer

    statement = build_postgres_cleanup_statement(
        {"users", "campaigns"},
        preparer,
    )

    assert statement == (
        "TRUNCATE TABLE test_asset_h_7e4c91a2d603.campaigns, "
        "test_asset_h_7e4c91a2d603.users"
    )
    assert "public" not in statement
    assert "alembic_version" not in statement
    assert "CASCADE" not in statement

    with pytest.raises(ValueError, match="version table"):
        build_postgres_cleanup_statement(
            {"alembic_version"},
            preparer,
        )
