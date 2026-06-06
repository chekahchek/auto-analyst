import configparser
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def _read_ini(path: Path) -> dict[str, str]:
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return {
        k.upper(): v.strip('"').strip("'")
        for section in parser.sections()
        for k, v in parser.items(section)
    }


class Settings(BaseModel):
    """Application configuration loaded from INI files.

    Reads ``values/{APP_ENV}.ini`` followed by ``values/secret.ini``.
    The only environment variable consulted is ``APP_ENV`` (defaults to ``dev``).

    To add config, add a field in lower case and add the corresponding key in INI files in upper case.
    """

    app_env: str
    db_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/auto_analyst"
    )
    moonshot_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    api_base_url: str = Field(default="")
    cost_budget: Decimal = Field(default=Decimal("1.00"))
    file_storage_path: Path = Field(default=Path("./data"))
    skills_dir: Path = Field(default=Path("./skills"))

    @classmethod
    def from_ini(cls, app_env: str | None = None) -> "Settings":
        env = app_env or os.environ.get("APP_ENV", "dev")
        backend_root = Path(__file__).resolve().parent.parent
        values_dir = backend_root / "values"

        env_ini = (
            _read_ini(values_dir / f"{env}.ini")
            if (values_dir / f"{env}.ini").exists()
            else {}
        )
        secret_ini = (
            _read_ini(values_dir / "secret.ini")
            if (values_dir / "secret.ini").exists()
            else {}
        )
        merged = {**env_ini, **secret_ini}

        kwargs: dict[str, Any] = {"app_env": env}
        for name, info in cls.model_fields.items():
            if name == "app_env":
                continue

            ini_key = name.upper()
            raw = merged.get(ini_key)

            if raw is None:
                if info.is_required():
                    raise ValueError(f"Missing required config key: {ini_key}")
                kwargs[name] = info.default
                continue

            if info.annotation is Path:
                path = Path(raw)
                kwargs[name] = backend_root / path if not path.is_absolute() else path
            else:
                kwargs[name] = raw

        return cls(**kwargs)
