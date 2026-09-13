import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, computed_field, field_validator

_CONFIG_FILENAME = "config.yaml"
_DB_FILENAME = "refree.db"
_DEFAULT_REFREE_DIR = Path.home() / ".refree" / "data"


class ConfigError(Exception):
    """Raised when the refree configuration cannot be loaded or is invalid."""


class _Settings(BaseModel):
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    refree_dir: Path = _DEFAULT_REFREE_DIR
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    @field_validator("app_port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if not 0 < value < 65536:
            msg = "app_port must be between 1 and 65535"
            raise ValueError(msg)
        return value

    @field_validator("refree_dir", mode="after")
    @classmethod
    def _validate_dir(cls, value: Path) -> Path:
        return value.expanduser()

    @computed_field
    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.refree_dir / _DB_FILENAME}"


def _candidate_paths() -> list[Path]:
    override = os.getenv("REFREE_CONFIG_FILE")
    if override:
        return [Path(override)]
    home = Path.home()
    return [home / ".refree" / _CONFIG_FILENAME]


def _resolve_config_path() -> Path:
    for candidate in _candidate_paths():
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(p) for p in _candidate_paths())
    msg = (
        "no refree config file found; searched: "
        f"{searched}. "
        "Create one with a 'refree_dir' and optional 'app_port', "
        "or set REFREE_CONFIG_FILE to its path."
    )
    raise ConfigError(msg)


def _load_settings() -> _Settings:
    path = _resolve_config_path()
    with path.open("r", encoding="utf-8") as handle:
        raw: Any = yaml.safe_load(handle)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        msg = (
            f"config file '{path}' must contain a top-level mapping, "
            f"got {type(raw).__name__}"
        )
        raise ConfigError(msg)
    try:
        return _Settings.model_validate(raw)
    except ValueError as exc:
        msg = f"invalid config in '{path}':\n{exc}"
        raise ConfigError(msg) from exc


def _ensure_refree_dir(settings: _Settings) -> None:
    settings.refree_dir.mkdir(parents=True, exist_ok=True)


settings = _load_settings()
_ensure_refree_dir(settings)

REFREE_DIR = settings.refree_dir

PDF_DIR = REFREE_DIR / "pdfs"
APP_HOST = settings.app_host
APP_PORT = settings.app_port
EMBEDDING_MODEL = settings.embedding_model
