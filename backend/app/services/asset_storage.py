import re
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4


_STORAGE_KEY_PATTERN = re.compile(r"[0-9a-f]{32}\.(?:png|jpe?g|webp|gif)\Z")


class AssetStorage(Protocol):
    def store(self, data: bytes, extension: str) -> str: ...

    def open(self, storage_key: str) -> BinaryIO: ...

    def delete(self, storage_key: str) -> None: ...


class LocalAssetStorage:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            from app.core.config import get_settings

            root = get_settings().asset_storage_path
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[2] / root
        self.root = root

    def store(self, data: bytes, extension: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        while True:
            key = f"{uuid4().hex}{extension}"
            path = self._path_for(key)
            try:
                with path.open("xb") as asset_file:
                    asset_file.write(data)
                return key
            except FileExistsError:
                continue
            except OSError:
                path.unlink(missing_ok=True)
                raise

    def path_for(self, storage_key: str) -> Path:
        path = self._path_for(storage_key)
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError("Asset file is unavailable.")
        return path

    def open(self, storage_key: str) -> BinaryIO:
        return self.path_for(storage_key).open("rb")

    def delete(self, storage_key: str) -> None:
        path = self._path_for(storage_key)
        if path.is_symlink():
            raise OSError("Asset storage key points to a symbolic link.")
        path.unlink(missing_ok=True)

    def _path_for(self, storage_key: str) -> Path:
        if _STORAGE_KEY_PATTERN.fullmatch(storage_key) is None:
            raise ValueError("Invalid asset storage key.")
        root = self.root.resolve()
        path = root / storage_key
        if path.parent != root:
            raise ValueError("Asset storage key escapes its storage directory.")
        return path
