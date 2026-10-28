"""Runtime configuration for the ML service.

The service reads the same ``config.php`` file as the PHP application so that
there is one source of truth for database credentials. Environment variables
take precedence, which keeps Docker and tests simple.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

_PHP_ENTRY = re.compile(r"['\"]([^'\"]+)['\"]\s*=>\s*['\"]((?:[^'\\]|\\.)*)['\"]")


def _unescape_php(value: str) -> str:
    return value.replace("\\'", "'").replace("\\\\", "\\")


def parse_php_config(path: Path) -> dict[str, str]:
    """Parse the flat ``var_export()`` array written by ``install.php``.

    The file is intentionally simple::

        <?php
        return array (
          'db.engine' => 'sqlite',
          'db.name' => 'phproject.db',
        );
    """
    if not path.is_file():
        return {}

    text = path.read_text(encoding="utf-8", errors="replace")
    return {key: _unescape_php(value) for key, value in _PHP_ENTRY.findall(text)}


def _env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value is not None and value != "":
            return value
    return default


@dataclass(frozen=True)
class Settings:
    env: str
    service_version: str
    internal_token: str
    project_root: Path
    config_path: Path
    db_engine: str
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    db_path: Path | None
    model_dir: Path
    legacy_dir: Path
    risk_cache_seconds: int
    default_capacity_hours: float

    @property
    def sqlalchemy_url(self) -> str:
        override = _env("ML_DATABASE_URL", "PHPROJECT_DATABASE_URL")
        if override:
            return override

        if self.db_engine == "sqlite":
            path = self.db_path or Path(self.db_name)
            return f"sqlite+pysqlite:///{path}"

        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{user}:{password}@{self.db_host}:{self.db_port}/"
            f"{quote_plus(self.db_name)}?charset=utf8mb4"
        )

    @property
    def auth_required(self) -> bool:
        return bool(self.internal_token)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(
        _env("PHPROJECT_ROOT", "ML_PROJECT_ROOT", default=str(Path(__file__).resolve().parents[2]))
    ).resolve()

    config_path = Path(
        _env("PHPROJECT_CONFIG_PATH", "ML_CONFIG_PATH", default=str(project_root / "config.php"))
    )
    config = parse_php_config(config_path)

    engine = (_env("PHPROJECT_DB_ENGINE", "ML_DB_ENGINE") or config.get("db.engine") or "sqlite").lower()
    db_name = _env("PHPROJECT_DB_NAME", "ML_DB_NAME") or config.get("db.name") or "phproject.db"

    db_path: Path | None = None
    if engine == "sqlite":
        candidate = Path(db_name)
        if not candidate.is_absolute() and db_name != ":memory:":
            candidate = (project_root / candidate).resolve()
        db_path = candidate

    model_dir = Path(_env("ML_MODEL_DIR", default=str(project_root / "ml-service" / "artifacts")))
    if not model_dir.is_absolute():
        model_dir = (project_root / model_dir).resolve()

    legacy_dir = Path(_env("ML_LEGACY_DIR", default=str(project_root / "ml")))
    if not legacy_dir.is_absolute():
        legacy_dir = (project_root / legacy_dir).resolve()

    return Settings(
        env=(_env("ML_ENV", default="dev") or "dev").lower(),
        service_version=_env("ML_SERVICE_VERSION", default="0.1.0") or "0.1.0",
        internal_token=_env("ML_INTERNAL_TOKEN", default="") or "",
        project_root=project_root,
        config_path=config_path,
        db_engine=engine,
        db_host=_env("PHPROJECT_DB_HOST", "ML_DB_HOST") or config.get("db.host", "127.0.0.1"),
        db_port=int(_env("PHPROJECT_DB_PORT", "ML_DB_PORT") or config.get("db.port", "3306")),
        db_user=_env("PHPROJECT_DB_USER", "ML_DB_USER") or config.get("db.user", "root"),
        db_password=(
            _env("PHPROJECT_DB_PASSWORD", "PHPROJECT_DB_PASS", "ML_DB_PASSWORD", "ML_DB_PASS")
            or config.get("db.pass", "")
        ),
        db_name=db_name,
        db_path=db_path,
        model_dir=model_dir,
        legacy_dir=legacy_dir,
        risk_cache_seconds=int(_env("ML_RISK_CACHE_SECONDS", default="300") or "300"),
        default_capacity_hours=float(_env("ML_CAPACITY_HOURS", default="40") or "40"),
    )
