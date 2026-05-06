"""Configuration loading for the Simple MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_ENV_FILE = Path(".env")


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings loaded from the environment."""

    tenable_access_key: str = field(repr=False)
    tenable_secret_key: str = field(repr=False)
    tenable_vendor: str
    tenable_product: str
    tenable_build: str = "1.0.0"


class ConfigurationError(RuntimeError):
    """Raised when required application configuration is missing."""


def load_dotenv(path: Path = DEFAULT_ENV_FILE) -> None:
    """Load simple KEY=VALUE pairs from a .env file into the environment."""

    if not path.exists():
        return

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            raise ConfigurationError(
                f"Invalid .env entry on line {line_number}: expected KEY=VALUE."
            )

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")

        if not key:
            raise ConfigurationError(
                f"Invalid .env entry on line {line_number}: key is empty."
            )

        os.environ.setdefault(key, value)


def get_settings() -> Settings:
    """Return validated settings for the application."""

    load_dotenv()

    values = {
        "tenable_access_key": os.environ.get("TENABLE_ACCESS_KEY", ""),
        "tenable_secret_key": os.environ.get("TENABLE_SECRET_KEY", ""),
        "tenable_vendor": os.environ.get("TENABLE_VENDOR", ""),
        "tenable_product": os.environ.get("TENABLE_PRODUCT", ""),
        "tenable_build": os.environ.get("TENABLE_BUILD", "1.0.0"),
    }
    missing = [
        env_name
        for field_name, env_name in (
            ("tenable_access_key", "TENABLE_ACCESS_KEY"),
            ("tenable_secret_key", "TENABLE_SECRET_KEY"),
            ("tenable_vendor", "TENABLE_VENDOR"),
            ("tenable_product", "TENABLE_PRODUCT"),
        )
        if not values[field_name]
    ]

    if missing:
        missing_vars = ", ".join(missing)
        raise ConfigurationError(
            f"Missing required environment variables: {missing_vars}"
        )

    return Settings(**values)
