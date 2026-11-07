from __future__ import annotations

import asyncio
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.test_environment import resolve_asset_migration_target


LEGACY_SCHEMA = "test_visual_g_eb8c40da20ae"
_SQLSTATE_PATTERN = re.compile(r"[0-9A-Z]{5}\Z")


def _require_interactive_console() -> None:
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise RuntimeError(
            "Run this script from an interactive terminal with hidden input support."
        )


def _build_test_database_url(password: str) -> str:
    return URL.create(
        drivername="postgresql+asyncpg",
        username="cronicas_local",
        password=password,
        host="127.0.0.1",
        port=5432,
        database="cronicas_do_reino_test",
    ).render_as_string(hide_password=False)


def _safe_database_error_summary(error: BaseException) -> str:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = getattr(current, "orig", None) or current.__cause__ or current.__context__

    sqlstate = next(
        (
            candidate
            for item in chain
            if (candidate := getattr(item, "sqlstate", None)) is not None
            and _SQLSTATE_PATTERN.fullmatch(candidate)
        ),
        None,
    )
    names = {type(item).__name__ for item in chain}

    if sqlstate == "28P01" or "InvalidPasswordError" in names:
        category = "authentication rejected (password invalid or role authentication denied)"
    elif sqlstate == "3D000" or "InvalidCatalogNameError" in names:
        category = "database name not found"
    elif sqlstate == "42501" or "InsufficientPrivilegeError" in names:
        category = "role lacks a required database privilege"
    elif "ConnectionRefusedError" in names:
        category = "TCP connection refused"
    elif "TimeoutError" in names or "ConnectionTimeoutError" in names:
        category = "connection timed out"
    elif "ConnectionResetError" in names or "ConnectionDoesNotExistError" in names:
        category = "connection was reset or closed during startup"
    else:
        category = "database connection/driver error (cause not classified)"

    safe_names = sorted(
        name
        for name in names
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name)
    )
    details = f"; SQLSTATE={sqlstate}" if sqlstate else ""
    if safe_names:
        details += f"; exception types={', '.join(safe_names[:4])}"
    return f"{category}{details}"


def _is_local_server_address(address: str | None) -> bool:
    if address is None:
        return False
    try:
        parsed_address = ipaddress.ip_address(address)
    except (TypeError, ValueError):
        return False
    if isinstance(parsed_address, ipaddress.IPv6Address) and parsed_address.ipv4_mapped:
        parsed_address = parsed_address.ipv4_mapped
    return parsed_address.is_loopback


def _is_local_configured_host(host: str | None, resolver=socket.getaddrinfo) -> bool:
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
    except (TypeError, ValueError):
        normalized_host = host.rstrip(".").casefold()
        if normalized_host != "localhost":
            return False
        try:
            results = resolver(
                normalized_host,
                5432,
                type=socket.SOCK_STREAM,
            )
        except OSError:
            return False
        addresses = [result[4][0] for result in results if result[4]]
        return bool(addresses) and all(
            _is_local_server_address(address) for address in addresses
        )
    return _is_local_server_address(host)


def _listener_processes_are_postgres(
    port: int,
    *,
    platform: str = os.name,
    run=subprocess.run,
) -> bool:
    if platform != "nt" or not isinstance(port, int) or not 1 <= port <= 65535:
        return False
    command = (
        f"$processNames = @(Get-NetTCPConnection -State Listen -LocalPort {port} "
        "-ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique | "
        "ForEach-Object { (Get-Process -Id $_ -ErrorAction Stop).ProcessName }); "
        "$processNames | ConvertTo-Json -Compress"
    )
    try:
        completed = run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        process_names = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    if isinstance(process_names, str):
        process_names = [process_names]
    return bool(process_names) and all(
        isinstance(name, str) and name.casefold() == "postgres"
        for name in process_names
    )


async def _inspect_target(schema_name: str) -> tuple:
    target = resolve_asset_migration_target(os.environ)
    if target.schema_name != schema_name:
        raise RuntimeError("The explicit test schema does not match the generated target.")
    configured_host_is_local = _is_local_configured_host(target.database_url.host)
    if (
        not configured_host_is_local
        or target.database_url.port != 5432
        or target.database_url.database != "cronicas_do_reino_test"
        or target.database_url.username != "cronicas_local"
    ):
        raise RuntimeError("The test connection target failed local safety validation.")
    listener_is_postgres = _listener_processes_are_postgres(5432)
    if not listener_is_postgres:
        raise RuntimeError(
            "The local port listener could not be verified as the PostgreSQL server process."
        )

    engine = create_async_engine(
        target.database_url,
        connect_args={
            "server_settings": {
                "default_transaction_read_only": "on",
                "search_path": "pg_catalog",
            },
            "timeout": 5,
        },
        pool_pre_ping=True,
    )
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT current_database(),
                               current_user,
                               current_schema(),
                               current_setting('search_path'),
                               inet_server_addr()::text,
                               inet_client_addr()::text,
                               inet_server_port(),
                               current_setting('transaction_read_only'),
                               role.rolsuper,
                               role.rolcreatedb,
                               role.rolcreaterole,
                               has_database_privilege(
                                   current_user, current_database(), 'CREATE'
                               ),
                               EXISTS (
                                   SELECT 1
                                   FROM pg_namespace
                                   WHERE nspname = :candidate_schema
                               ),
                               EXISTS (
                                   SELECT 1
                                   FROM pg_namespace
                                   WHERE nspname = :legacy_schema
                               ),
                               (
                                   SELECT count(*)::integer
                                   FROM pg_tables
                                   WHERE schemaname = :legacy_schema
                               ),
                               EXISTS (
                                   SELECT 1
                                   FROM pg_tables
                                   WHERE schemaname = :legacy_schema
                                     AND tablename = 'alembic_version'
                               )
                        FROM pg_roles AS role
                        WHERE role.rolname = current_user
                        """
                    ),
                    {
                        "candidate_schema": schema_name,
                        "legacy_schema": LEGACY_SCHEMA,
                    },
                )
            ).one()
    finally:
        await engine.dispose()

    (
        database,
        role,
        current_schema,
        search_path,
        server_address,
        client_address,
        port,
        read_only,
        is_superuser,
        can_create_database,
        can_create_roles,
        can_create_schema,
        candidate_exists,
        legacy_exists,
    ) = row[:14]

    if database != "cronicas_do_reino_test":
        raise RuntimeError("Connected database is not the authorized test database.")
    if role != "cronicas_local":
        raise RuntimeError("Authenticated role is not the authorized restricted role.")
    is_local_server = _is_local_server_address(server_address)
    is_local_client = _is_local_server_address(client_address)
    is_expected_port = port == 5432
    if not is_local_server or not is_local_client or not is_expected_port:
        raise RuntimeError(
            "PostgreSQL endpoint validation failed "
                f"(configured_host_loopback={configured_host_is_local}, "
            f"server_socket_loopback={is_local_server}, "
            f"client_peer_loopback={is_local_client}, "
                f"local_listener_is_postgres={listener_is_postgres}, "
                f"port_5432={is_expected_port})."
            )
    if current_schema != "pg_catalog" or search_path != "pg_catalog":
        raise RuntimeError("The read-only connection is not restricted to pg_catalog.")
    if read_only != "on":
        raise RuntimeError("The PostgreSQL probe is not read-only.")
    if is_superuser or can_create_database or can_create_roles:
        raise RuntimeError("The authenticated role is not sufficiently restricted.")
    if not can_create_schema:
        raise RuntimeError("The role lacks CREATE privilege on the authorized test database.")
    if candidate_exists:
        raise RuntimeError("The generated test schema already exists; no write was attempted.")
    if schema_name == LEGACY_SCHEMA:
        raise RuntimeError("The legacy visual schema cannot be used as the new target.")
    if not legacy_exists:
        raise RuntimeError("The previously existing legacy visual schema was not found.")

    return row


def main() -> int:
    _require_interactive_console()
    schema_name = f"test_asset_h_{secrets.token_hex(6)}"
    password = getpass.getpass("Senha PostgreSQL de cronicas_local (entrada oculta): ")
    if not password:
        raise RuntimeError("A senha não pode estar vazia.")

    os.environ["TEST_DATABASE_URL"] = _build_test_database_url(password)
    os.environ["TEST_ASSET_SCHEMA"] = schema_name
    del password

    try:
        row = asyncio.run(_inspect_target(schema_name))
    finally:
        os.environ.pop("TEST_DATABASE_URL", None)
        os.environ.pop("TEST_ASSET_SCHEMA", None)

    print("Pré-validação somente leitura aprovada; nenhuma escrita foi realizada.")
    print("Host: 127.0.0.1:5432")
    print(f"Banco confirmado: {row[0]}")
    print(f"Role autenticada: {row[1]}")
    print(f"Schema isolado candidato: {schema_name} (ainda não existe)")
    print(
        f"Schema visual antigo preservado: {LEGACY_SCHEMA}; "
        f"tabelas={row[14]}; alembic_version={bool(row[15])}"
    )
    print("Role restrita; CREATE no banco de teste confirmado.")
    print(
        "Envie estes resultados para confirmação antes de qualquer criação de schema "
        "ou execução de migration."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, EOFError) as error:
        print(f"Pré-validação interrompida: {error}", file=sys.stderr)
        raise SystemExit(2) from None
    except (SQLAlchemyError, ValueError, TimeoutError) as error:
        print(
            f"Pré-validação falhou: {_safe_database_error_summary(error)}. "
            "Nenhuma escrita foi realizada.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
