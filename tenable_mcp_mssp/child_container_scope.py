"""Configured positive allowlist for MSSP child container actions."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from tenable_mcp_mssp.config import ConfigurationError, load_dotenv


CHILD_CONTAINER_SCOPE_FILE_ENV = "TENABLE_MCP_MSSP_CHILD_CONTAINER_SCOPE_FILE"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ChildContainerScope:
    """Configured positive allowlist for child container UUIDs."""

    scope_enabled: bool
    source: str | None
    allowed_child_container_uuids: frozenset[str]

    @property
    def count(self) -> int:
        """Return the number of explicitly allowed child container UUIDs."""

        return len(self.allowed_child_container_uuids)

    def allows(self, child_container_uuid: str) -> bool:
        """Return whether the child UUID is allowed by this scope."""

        if not self.scope_enabled:
            return True

        return child_container_uuid in self.allowed_child_container_uuids

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly scope report."""

        return {
            "scope_enabled": self.scope_enabled,
            "source": self.source,
            "count": self.count,
            "allowed_child_container_uuids": sorted(
                self.allowed_child_container_uuids
            ),
        }


@lru_cache(maxsize=1)
def load_child_container_scope() -> ChildContainerScope:
    """Load the configured child container allowlist scope."""

    load_dotenv()
    configured_path = os.environ.get(CHILD_CONTAINER_SCOPE_FILE_ENV, "").strip()
    if not configured_path:
        logger.info("Child container scope is disabled.")
        return ChildContainerScope(
            scope_enabled=False,
            source=None,
            allowed_child_container_uuids=frozenset(),
        )

    scope_path = _resolve_scope_path(configured_path)
    try:
        lines = scope_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed to load child container scope file %s.", scope_path)
        raise ConfigurationError(
            f"Unable to read child container scope file: {scope_path}"
        ) from exc

    allowed_uuids = frozenset(_parse_scope_lines(lines, scope_path))
    logger.info(
        "Child container scope is enabled from %s with %d UUIDs.",
        scope_path,
        len(allowed_uuids),
    )
    return ChildContainerScope(
        scope_enabled=True,
        source=str(scope_path),
        allowed_child_container_uuids=allowed_uuids,
    )


def get_child_container_scope() -> dict[str, object]:
    """Return the configured child container scope report."""

    return load_child_container_scope().to_dict()


def is_child_container_in_scope(child_container_uuid: str) -> bool:
    """Return whether a child container UUID is allowed by configured scope."""

    return load_child_container_scope().allows(child_container_uuid)


def _resolve_scope_path(configured_path: str) -> Path:
    """Resolve a configured scope path against the current working directory."""

    scope_path = Path(configured_path).expanduser()
    if not scope_path.is_absolute():
        scope_path = Path.cwd() / scope_path

    return scope_path.resolve()


def _parse_scope_lines(lines: list[str], scope_path: Path) -> set[str]:
    """Parse scope file lines into validated canonical UUID strings."""

    allowed_uuids: set[str] = set()
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            child_uuid = str(UUID(line))
        except ValueError as exc:
            logger.warning(
                "Invalid child container scope entry in %s on line %d.",
                scope_path,
                line_number,
            )
            raise ConfigurationError(
                "Invalid child container scope entry "
                f"on line {line_number}: expected UUID."
            ) from exc

        allowed_uuids.add(child_uuid)

    return allowed_uuids
