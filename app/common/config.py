import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.getenv("REFREE_ENV_FILE"))


class _MissingSettingError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Missing required environment variable: {name}")
        self.name = name


class _InvalidPathError(Exception):
    def __init__(self, name: str, path: str) -> None:
        super().__init__(
            f"Cannot find file '{path}' passed in environment variable '{name}'"
        )
        self.name = name
        self.path = path


def _optional_str(name: str) -> str | None:
    return os.getenv(name)


def _require_bool(name: str) -> bool:
    value = _optional_str(name)
    if value is None or value == "":
        raise _MissingSettingError(name)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require_str(name: str) -> str:
    value = _optional_str(name)
    if value is None:
        raise _MissingSettingError(name)
    return value


def _require_path(name: str) -> Path:
    value = _optional_str(name)
    if value is None:
        raise _MissingSettingError(name)
    return Path(value)


def _require_path_exists(name: str) -> Path:
    path = _require_path(name)
    if not path.exists():
        raise _InvalidPathError(name, str(path))
    return path


def _database_url() -> str:
    url = _optional_str("DATABASE_URL")
    if url:
        return url
    db_path = _optional_str("DATABASE_PATH")
    return f"sqlite:///{db_path or 'refree.db'}"


DATABASE_URL = _database_url()
APP_PORT = int(_require_str("APP_PORT"))
