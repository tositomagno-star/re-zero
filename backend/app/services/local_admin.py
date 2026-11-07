from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import ipaddress

from sqlalchemy import select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import User
from app.services.admin_bootstrap import AdminBootstrapError, validate_admin_credentials

_LOCAL_ADMIN_DATABASE = "cronicas_do_reino_dev"
_LOCAL_ADMIN_PORT = 5432


class LocalAdminError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalAdminTarget:
    database_url: URL


def resolve_local_admin_target(
    environment: Mapping[str, str],
    *,
    database_url: str | None,
) -> LocalAdminTarget:
    if environment.get("APP_ENVIRONMENT") != "development":
        raise LocalAdminError(
            "A criação de administrador local exige APP_ENVIRONMENT=development."
        )
    if not database_url:
        raise LocalAdminError("A URL do banco de desenvolvimento não está configurada.")
    try:
        parsed_url = make_url(database_url)
    except (ArgumentError, ValueError) as error:
        raise LocalAdminError("A URL do banco de desenvolvimento é inválida.") from error

    if (
        parsed_url.drivername != "postgresql+asyncpg"
        or parsed_url.database != _LOCAL_ADMIN_DATABASE
        or parsed_url.port != _LOCAL_ADMIN_PORT
        or not parsed_url.username
    ):
        raise LocalAdminError(
            "A operação aceita somente cronicas_do_reino_dev em PostgreSQL local na porta 5432."
        )
    try:
        address = ipaddress.ip_address(parsed_url.host or "")
    except ValueError as error:
        raise LocalAdminError(
            "O host deve ser um endereço IP loopback literal; nomes de host não são aceitos."
        ) from error
    if not address.is_loopback:
        raise LocalAdminError("O banco de administrador local não pode ser remoto.")
    return LocalAdminTarget(database_url=parsed_url)


async def verify_local_admin_database(
    session: AsyncSession,
    target: LocalAdminTarget,
) -> None:
    identity = (
        await session.execute(
            text(
                "SELECT current_database(), current_user, "
                "inet_server_addr()::text, current_schema()"
            )
        )
    ).one()
    try:
        server_address = ipaddress.ip_interface(identity[2]).ip if identity[2] else None
    except ValueError as error:
        raise LocalAdminError(
            "A identidade do servidor PostgreSQL não pôde ser validada."
        ) from error
    if (
        identity[0] != _LOCAL_ADMIN_DATABASE
        or identity[1] != target.database_url.username
        or server_address is None
        or not server_address.is_loopback
        or identity[3] != "public"
    ):
        raise LocalAdminError(
            "A conexão não corresponde ao banco local autorizado cronicas_do_reino_dev."
        )


async def create_local_admin(
    session: AsyncSession,
    *,
    username: str,
    password: str,
) -> User:
    try:
        normalized_username, username_key = validate_admin_credentials(username, password)
    except AdminBootstrapError as error:
        raise LocalAdminError(str(error)) from error
    existing = await session.scalar(
        select(User.id).where(User.username_key == username_key).limit(1)
    )
    if existing is not None:
        raise LocalAdminError("Esse username já está cadastrado; nenhuma conta foi alterada.")

    user = User(
        username=normalized_username,
        username_key=username_key,
        email=None,
        password_hash=hash_password(password),
        display_name=normalized_username,
        is_admin=True,
        status="active",
    )
    session.add(user)
    await session.flush()
    return user
