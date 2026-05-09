"""Configuration loading for the Tenable MCP MSSP server."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from tenable_mcp_mssp import __version__


DEFAULT_ENV_FILE = Path(".env")
MSSP_PORTAL_ACCESS_KEY_ENV = "TENABLE_MSSP_PORTAL_ACCESS_KEY"
MSSP_PORTAL_SECRET_KEY_ENV = "TENABLE_MSSP_PORTAL_SECRET_KEY"
INTEGRATION_VENDOR = "github.com/andrewspearson"
INTEGRATION_PRODUCT = "tenable-mcp-mssp"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings loaded from the environment."""

    mssp_portal_access_key: str = field(repr=False)
    mssp_portal_secret_key: str = field(repr=False)
    tenable_vendor: str = INTEGRATION_VENDOR
    tenable_product: str = INTEGRATION_PRODUCT
    tenable_build: str = __version__


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
        "mssp_portal_access_key": os.environ.get(MSSP_PORTAL_ACCESS_KEY_ENV, ""),
        "mssp_portal_secret_key": os.environ.get(MSSP_PORTAL_SECRET_KEY_ENV, ""),
    }
    missing = [
        env_name
        for field_name, env_name in (
            ("mssp_portal_access_key", MSSP_PORTAL_ACCESS_KEY_ENV),
            ("mssp_portal_secret_key", MSSP_PORTAL_SECRET_KEY_ENV),
        )
        if not values[field_name]
    ]

    if missing:
        missing_vars = ", ".join(missing)
        raise ConfigurationError(
            f"Missing required environment variables: {missing_vars}"
        )

    settings = Settings(**values)
    logger.info("Loaded Tenable MCP MSSP configuration.")
    return settings
