from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import ipaddress
import re

from sqlalchemy.exc import ArgumentError
from sqlalchemy.engine import URL, make_url


_SCHEMA_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}\Z")
_NON_PRODUCTION_NAME = re.compile(r"(^|[_-])(dev|test)([_-]|$)", re.IGNORECASE)
_LOCAL_HOSTS = {"localhost", "localhost.localdomain"}


@dataclass(frozen=True)
class ProductionDatabaseTarget:
    database_url: URL
    database_name: str
    host: str
    schema_name: str


def resolve_production_database_target(
    environment: Mapping[str, str],
    *,
    database_url: str | None,
    require_bootstrap_enabled: bool = False,
    require_migrations_enabled: bool = False,
) -> ProductionDatabaseTarget:
    if environment.get("APP_ENVIRONMENT") != "production":
        raise RuntimeError("The administrative operation requires APP_ENVIRONMENT=production.")
    if environment.get("ADMIN_OPERATION_TARGET") != "production":
        raise RuntimeError("The administrative operation target is not explicitly authorized.")
    if (
        require_migrations_enabled
        and environment.get("ADMIN_MIGRATIONS_ENABLED") != "true"
    ):
        raise RuntimeError("Production migrations are not explicitly enabled.")
    if require_bootstrap_enabled and environment.get("ADMIN_BOOTSTRAP_ENABLED") != "true":
        raise RuntimeError("Administrative bootstrap is not explicitly enabled.")

    expected_database = environment.get("ADMIN_EXPECTED_DATABASE", "").strip()
    expected_host = environment.get("ADMIN_EXPECTED_DATABASE_HOST", "").strip().casefold()
    schema_name = environment.get("ADMIN_EXPECTED_DATABASE_SCHEMA", "").strip()
    if not expected_database or not expected_host or not _SCHEMA_NAME.fullmatch(schema_name):
        raise RuntimeError("The expected production database identity is incomplete.")
    if _NON_PRODUCTION_NAME.search(expected_database):
        raise RuntimeError("The expected database name is not authorized for production.")
    if expected_host in _LOCAL_HOSTS:
        raise RuntimeError("A local database host is not authorized for production.")
    try:
        address = ipaddress.ip_address(expected_host)
    except ValueError:
        address = None
    if address is not None and (address.is_loopback or address.is_unspecified):
        raise RuntimeError("A local database host is not authorized for production.")
    if not database_url:
        raise RuntimeError("The production database URL is unavailable.")
    try:
        parsed_url = make_url(database_url)
    except (ArgumentError, ValueError) as error:
        raise RuntimeError("The production database URL is invalid.") from error
    if (
        parsed_url.drivername != "postgresql+asyncpg"
        or parsed_url.database != expected_database
        or (parsed_url.host or "").casefold() != expected_host
    ):
        raise RuntimeError("The configured database does not match the authorized target.")
    return ProductionDatabaseTarget(
        database_url=parsed_url,
        database_name=expected_database,
        host=expected_host,
        schema_name=schema_name,
    )
