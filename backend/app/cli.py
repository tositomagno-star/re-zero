import argparse
import asyncio
import getpass
import ipaddress
import logging
import os
from pathlib import Path
import platform
import re
import stat
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.core.config import get_settings
from app.deployment_targets import (
    ProductionDatabaseTarget,
    resolve_production_database_target,
)
from app.models import User
from app.schemas.auth import USERNAME_PATTERN
from app.services.admin_bootstrap import (
    AdminBootstrapError,
    bootstrap_first_admin,
    issue_admin_bootstrap_grant,
)
from app.services.local_admin import (
    LocalAdminError,
    LocalAdminTarget,
    create_local_admin,
    resolve_local_admin_target,
    verify_local_admin_database,
)
from app.test_environment import IsolatedTestTarget, resolve_admin_test_target

logger = logging.getLogger(__name__)
_BOOTSTRAP_SECRET_DIRECTORY = Path("/run/admin-bootstrap")


def _read_admin_credentials() -> tuple[str, str]:
    username = input("Admin username (3-32 letters, numbers or underscores): ").strip()
    if re.fullmatch(USERNAME_PATTERN, username) is None:
        raise ValueError("Username must contain 3-32 letters, numbers or underscores.")

    password = getpass.getpass("Admin password (at least 12 characters): ")
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Admin password must contain between 12 and 128 characters.")
    confirmation = getpass.getpass("Confirm admin password: ")
    if password != confirmation:
        raise ValueError("The password confirmation does not match.")
    return username, password


async def _create_admin(
    username: str,
    password: str,
    target: IsolatedTestTarget,
) -> None:
    username_key = username.casefold()
    admin_engine = create_async_engine(
        target.database_url,
        connect_args={"server_settings": {"search_path": target.schema_name}},
        pool_pre_ping=True,
    )
    admin_session = async_sessionmaker(admin_engine, expire_on_commit=False)
    try:
        async with admin_session() as session:
            identity = (
                await session.execute(
                    text(
                        "SELECT current_database(), current_user, current_schema(), "
                        "current_setting('search_path'), inet_server_addr()::text"
                    )
                )
            ).one()
            try:
                server_address = ipaddress.ip_address(identity[4])
                if isinstance(server_address, ipaddress.IPv6Address):
                    server_address = server_address.ipv4_mapped or server_address
            except ValueError:
                server_address = None
            if (
                identity[0] != "cronicas_do_reino_test"
                or identity[1] != target.database_url.username
                or identity[2] != target.schema_name
                or identity[3] != target.schema_name
                or server_address is None
                or not server_address.is_loopback
            ):
                raise RuntimeError(
                    "Administrator creation refused: database session is not the "
                    "authorized local test target."
                )

            existing = await session.scalar(
                select(User.id).where(User.username_key == username_key)
            )
            if existing is not None:
                raise ValueError("An account with this username already exists.")
            session.add(
                User(
                    username=username,
                    username_key=username_key,
                    email=None,
                    password_hash=hash_password(password),
                    display_name=username,
                    is_admin=True,
                    status="active",
                )
            )
            await session.commit()
    finally:
        await admin_engine.dispose()


async def _verify_local_admin_target(target: LocalAdminTarget) -> None:
    engine = create_async_engine(target.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await verify_local_admin_database(session, target)
            await session.rollback()
    finally:
        await engine.dispose()


async def _create_local_admin(
    target: LocalAdminTarget,
    *,
    username: str,
    password: str,
) -> str:
    engine = create_async_engine(target.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            async with session.begin():
                await verify_local_admin_database(session, target)
                user = await create_local_admin(
                    session,
                    username=username,
                    password=password,
                )
                created_username = user.username
            return created_username
    finally:
        await engine.dispose()


def _production_bootstrap_target(confirmation: str) -> ProductionDatabaseTarget:
    if platform.system() != "Linux":
        raise AdminBootstrapError("O bootstrap administrativo só pode ser executado no perfil Linux.")
    if confirmation != "production":
        raise AdminBootstrapError("Confirmação explícita do ambiente de produção obrigatória.")
    return resolve_production_database_target(
        os.environ,
        database_url=os.environ.get("DATABASE_URL"),
        require_bootstrap_enabled=True,
    )


def _operator_identity() -> str:
    get_uid = getattr(os, "getuid", None)
    if not callable(get_uid):
        raise AdminBootstrapError("Não foi possível identificar o operador do processo.")
    return f"uid:{get_uid()}"[:128]


def _validate_secret_file_path(path: Path) -> Path:
    if not path.is_absolute():
        raise AdminBootstrapError("O arquivo temporário deve usar um caminho absoluto em /run.")
    try:
        resolved_directory = path.parent.resolve(strict=True)
        allowed_directory = _BOOTSTRAP_SECRET_DIRECTORY.resolve(strict=True)
    except OSError as error:
        raise AdminBootstrapError("O diretório temporário protegido não está disponível.") from error
    if resolved_directory != allowed_directory or path.name in {"", ".", ".."}:
        raise AdminBootstrapError(
            "O segredo temporário deve ficar diretamente em /run/admin-bootstrap."
        )
    try:
        directory_metadata = resolved_directory.stat()
    except OSError as error:
        raise AdminBootstrapError(
            "O diretório temporário protegido não está disponível."
        ) from error
    get_euid = getattr(os, "geteuid", None)
    if (
        not stat.S_ISDIR(directory_metadata.st_mode)
        or (os.name == "posix" and stat.S_IMODE(directory_metadata.st_mode) != 0o700)
        or (callable(get_euid) and directory_metadata.st_uid != get_euid())
    ):
        raise AdminBootstrapError(
            "O diretório temporário precisa pertencer ao operador e ter modo 0700."
        )
    return path


def _store_bootstrap_secret(path: Path, secret: str) -> None:
    path = _validate_secret_file_path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii", closefd=False) as secret_file:
            secret_file.write(secret)
            secret_file.flush()
        os.fsync(descriptor)
    except OSError:
        os.close(descriptor)
        path.unlink(missing_ok=True)
        raise
    else:
        os.close(descriptor)


def _read_bootstrap_secret(path: Path) -> str:
    path = _validate_secret_file_path(path)
    try:
        metadata = path.lstat()
    except OSError as error:
        raise AdminBootstrapError("O segredo temporário não está disponível.") from error
    if not stat.S_ISREG(metadata.st_mode) or (
        os.name == "posix" and stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise AdminBootstrapError("As permissões do segredo temporário não são seguras.")
    if metadata.st_size < 32 or metadata.st_size > 256:
        raise AdminBootstrapError("O segredo temporário tem formato inválido.")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened_metadata = os.fstat(descriptor)
        get_euid = getattr(os, "geteuid", None)
        if (
            not stat.S_ISREG(opened_metadata.st_mode)
            or (os.name == "posix" and stat.S_IMODE(opened_metadata.st_mode) != 0o600)
            or opened_metadata.st_ino != metadata.st_ino
            or (callable(get_euid) and opened_metadata.st_uid != get_euid())
        ):
            raise AdminBootstrapError("As permissões do segredo temporário não são seguras.")
        with os.fdopen(descriptor, "r", encoding="ascii") as secret_file:
            descriptor = None
            secret = secret_file.read(257)
    except AdminBootstrapError:
        raise
    except (OSError, UnicodeError) as error:
        raise AdminBootstrapError("O segredo temporário não pôde ser lido.") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(secret) < 32 or len(secret) > 256:
        raise AdminBootstrapError("O segredo temporário tem formato inválido.")
    return secret


def _confirm_production_target(target: ProductionDatabaseTarget) -> None:
    print(
        "Alvo administrativo: produção "
        f"(host={target.host}, database={target.database_name}, schema={target.schema_name})."
    )
    confirmation = input("Digite production para confirmar o alvo: ").strip()
    if confirmation != "production":
        raise AdminBootstrapError("Operação cancelada; nenhum dado foi alterado.")


async def _verify_production_database(
    session,
    target: ProductionDatabaseTarget,
) -> None:
    identity = (
        await session.execute(
            text("SELECT current_database(), current_schema(), current_setting('search_path')")
        )
    ).one()
    if identity[0] != target.database_name or identity[1] != target.schema_name:
        raise AdminBootstrapError(
            "A identidade da conexão não corresponde ao alvo de produção autorizado."
        )
    if identity[2] != target.schema_name:
        raise AdminBootstrapError(
            "O search_path da conexão não corresponde ao schema autorizado."
        )


async def _issue_production_bootstrap(
    target: ProductionDatabaseTarget,
    secret_path: Path,
) -> str:
    actor = _operator_identity()
    operation_id = str(uuid4())
    engine = create_async_engine(target.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    committed = False
    secret_created = False

    def store_secret(secret: str) -> None:
        nonlocal secret_created
        _store_bootstrap_secret(secret_path, secret)
        secret_created = True

    try:
        async with session_factory() as session:
            await _verify_production_database(session, target)
            await session.rollback()
            async with session.begin():
                operation = await issue_admin_bootstrap_grant(
                    session,
                    actor=actor,
                    store_secret=store_secret,
                )
            operation_id = operation.operation_id
            committed = True
            return operation_id
    finally:
        if not committed and secret_created:
            secret_path.unlink(missing_ok=True)
        await engine.dispose()


async def _create_first_production_admin(
    target: ProductionDatabaseTarget,
    *,
    username: str,
    password: str,
    secret: str,
) -> tuple[str, str]:
    actor = _operator_identity()
    command_id = str(uuid4())
    engine = create_async_engine(target.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await _verify_production_database(session, target)
            await session.rollback()
            async with session.begin():
                user, operation_id = await bootstrap_first_admin(
                    session,
                    username=username,
                    password=password,
                    secret=secret,
                    actor=actor,
                )
                user_id = str(user.id)
            return user_id, operation_id
    except SQLAlchemyError as error:
        logger.error(
            "Administrative bootstrap failed safely operation_id=%s error_type=%s",
            command_id,
            type(error).__name__,
        )
        raise
    finally:
        await engine.dispose()


def _prepare_bootstrap_command(arguments: argparse.Namespace) -> None:
    target = _production_bootstrap_target(arguments.confirm_environment)
    _confirm_production_target(target)
    operation_id = asyncio.run(
        _issue_production_bootstrap(target, Path(arguments.secret_file))
    )
    print(
        "Autorização temporária emitida; o segredo foi gravado somente no arquivo protegido. "
        f"Operação: {operation_id}. Validade: 15 minutos."
    )


def _bootstrap_admin_command(arguments: argparse.Namespace) -> None:
    target = _production_bootstrap_target(arguments.confirm_environment)
    _confirm_production_target(target)
    secret_path = Path(arguments.secret_file)
    secret = _read_bootstrap_secret(secret_path)
    username = input("Nome de usuário administrativo (3-32 caracteres): ").strip()
    password = getpass.getpass("Senha administrativa (12-128 caracteres): ")
    confirmation = getpass.getpass("Confirme a senha administrativa: ")
    if password != confirmation:
        raise AdminBootstrapError("A confirmação da senha não corresponde.")
    user_id, operation_id = asyncio.run(
        _create_first_production_admin(
            target,
            username=username,
            password=password,
            secret=secret,
        )
    )
    try:
        secret_path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning(
            "Consumed bootstrap secret file needs manual removal operation_id=%s",
            operation_id,
        )
        print("Bootstrap concluído; remova manualmente o arquivo temporário informado.")
    print(
        "Primeiro administrador criado. "
        f"Identificador da operação: {operation_id}; usuário: {user_id}."
    )


def _create_local_admin_command() -> None:
    settings = get_settings()
    environment = dict(os.environ)
    environment["APP_ENVIRONMENT"] = settings.app_environment or ""
    target = resolve_local_admin_target(
        environment,
        database_url=settings.database_url,
    )
    try:
        asyncio.run(_verify_local_admin_target(target))
    except SQLAlchemyError as error:
        logger.error(
            "Local administrator target verification failed safely error_type=%s",
            type(error).__name__,
        )
        raise SystemExit(
            "Não foi possível verificar o PostgreSQL local; nenhuma conta foi alterada."
        ) from None
    print("Destino confirmado: development / cronicas_do_reino_dev em PostgreSQL local.")

    username = input("Username administrativo (3-32 letras, números ou _): ").strip()
    if re.fullmatch(USERNAME_PATTERN, username) is None:
        raise SystemExit("Username inválido; use de 3 a 32 letras, números ou _.")
    password = getpass.getpass("Senha administrativa (12-128 caracteres): ")
    confirmation = getpass.getpass("Confirme a senha administrativa: ")
    if password != confirmation:
        raise SystemExit("A confirmação da senha não corresponde.")

    try:
        created_username = asyncio.run(
            _create_local_admin(
                target,
                username=username,
                password=password,
            )
        )
    except LocalAdminError as error:
        raise SystemExit(str(error)) from None
    except SQLAlchemyError as error:
        logger.error(
            "Local administrator creation failed safely error_type=%s",
            type(error).__name__,
        )
        raise SystemExit(
            "A operação foi revertida; verifique o banco local e se o username já existe."
        ) from None
    print(f"Administrador local criado com sucesso: {created_username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Crônicas do Reino administration tools")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "create-admin",
        help="Create a synthetic administrator in an authorized local test schema only",
    )
    subcommands.add_parser(
        "create-local-admin",
        help="Create a new administrator only in the verified local development database",
    )
    for command, help_text in (
        ("prepare-admin-bootstrap", "Issue a one-use production bootstrap authorization"),
        ("bootstrap-admin", "Create the first production administrator"),
    ):
        command_parser = subcommands.add_parser(command, help=help_text)
        command_parser.add_argument("--secret-file", required=True)
        command_parser.add_argument(
            "--confirm-environment",
            choices=["production"],
            required=True,
        )
    arguments = parser.parse_args()
    if arguments.command == "create-admin":
        if os.environ.get("APP_ENVIRONMENT") == "production":
            raise SystemExit("create-admin is test-only; production execution is refused.")
        target = resolve_admin_test_target(
            os.environ,
            legacy_database_url=os.environ.get("DATABASE_URL"),
        )
        if target is None:
            raise RuntimeError(
                "Set TEST_DATABASE_URL and TEST_ASSET_SCHEMA, or provide an authorized "
                "VISUAL_TEST_SCHEMA with an explicit test database URL."
            )
        username, password = _read_admin_credentials()
        asyncio.run(_create_admin(username, password, target))
        print("Synthetic administrator created in the isolated test target.")
    elif arguments.command == "create-local-admin":
        try:
            _create_local_admin_command()
        except LocalAdminError as error:
            raise SystemExit(str(error)) from None
    elif arguments.command == "prepare-admin-bootstrap":
        try:
            _prepare_bootstrap_command(arguments)
        except AdminBootstrapError as error:
            raise SystemExit(str(error)) from None
        except SQLAlchemyError as error:
            logger.error("Bootstrap grant issuance failed error_type=%s", type(error).__name__)
            raise SystemExit("A autorização não foi emitida; verifique a migration e o log operacional.") from None
    elif arguments.command == "bootstrap-admin":
        try:
            _bootstrap_admin_command(arguments)
        except AdminBootstrapError as error:
            raise SystemExit(str(error)) from None
        except SQLAlchemyError as error:
            logger.error("Bootstrap admin creation failed error_type=%s", type(error).__name__)
            raise SystemExit("A operação foi revertida; consulte o log operacional sem repetir a concessão.") from None


if __name__ == "__main__":
    main()
