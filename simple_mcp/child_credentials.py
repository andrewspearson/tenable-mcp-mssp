"""In-memory storage for temporary child API credentials."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


SECRET_FIELDS = {"access_key", "secret_key"}


@dataclass(frozen=True, slots=True)
class ChildCredential:
    """Temporary API credentials for a Tenable MSSP child container."""

    child_container_uuid: str
    access_key: str
    secret_key: str
    keys_expiration_epoch_seconds: int | None = None
    metadata: dict[str, Any] | None = None

    def is_expired(self, now: int | None = None) -> bool:
        """Return whether the credential is expired."""

        if self.keys_expiration_epoch_seconds is None:
            return False

        current_time = int(time.time()) if now is None else now
        return self.keys_expiration_epoch_seconds <= current_time

    def public_metadata(self) -> dict[str, Any]:
        """Return non-secret credential metadata."""

        metadata = dict(self.metadata or {})
        metadata["child_container_uuid"] = self.child_container_uuid
        metadata["keys_expiration_epoch_seconds"] = (
            self.keys_expiration_epoch_seconds
        )
        metadata["stored"] = True
        return metadata


class ChildCredentialStoreError(RuntimeError):
    """Raised when temporary child credentials are invalid or unavailable."""


class ChildCredentialStore:
    """In-memory store for temporary child API credentials."""

    def __init__(self, clock: Any = time.time) -> None:
        self._credentials: dict[str, ChildCredential] = {}
        self._clock = clock

    def store(self, response: dict[str, Any]) -> ChildCredential:
        """Store credentials from a Tenable child key generation response."""

        if not isinstance(response, dict):
            raise ChildCredentialStoreError(
                "Credential response must be an object."
            )

        child_container_uuid = _require_non_empty_string(
            response.get("child_container_uuid"),
            "child_container_uuid",
        )
        access_key = _require_non_empty_string(
            response.get("access_key"),
            "access_key",
        )
        secret_key = _require_non_empty_string(
            response.get("secret_key"),
            "secret_key",
        )
        expiration = _parse_expiration(
            response.get("keys_expiration_epoch_seconds")
        )

        metadata = {
            key: value
            for key, value in response.items()
            if key not in SECRET_FIELDS
        }
        credential = ChildCredential(
            child_container_uuid=child_container_uuid,
            access_key=access_key,
            secret_key=secret_key,
            keys_expiration_epoch_seconds=expiration,
            metadata=metadata,
        )

        if credential.is_expired(self._now()):
            raise ChildCredentialStoreError("Child credentials are expired.")

        self._credentials[child_container_uuid] = credential
        return credential

    def get(self, child_container_uuid: str) -> ChildCredential:
        """Return stored credentials for a child container."""

        clean_uuid = _require_non_empty_string(
            child_container_uuid,
            "child_container_uuid",
        )
        credential = self._credentials.get(clean_uuid)

        if credential is None:
            raise ChildCredentialStoreError(
                "No stored child credentials found for child_container_uuid."
            )

        if credential.is_expired(self._now()):
            self.remove(clean_uuid)
            raise ChildCredentialStoreError("Stored child credentials expired.")

        return credential

    def remove(self, child_container_uuid: str) -> None:
        """Remove stored credentials for a child container."""

        clean_uuid = _require_non_empty_string(
            child_container_uuid,
            "child_container_uuid",
        )
        self._credentials.pop(clean_uuid, None)

    def clear_expired(self) -> None:
        """Remove expired credentials from the store."""

        now = self._now()
        expired_uuids = [
            child_uuid
            for child_uuid, credential in self._credentials.items()
            if credential.is_expired(now)
        ]

        for child_uuid in expired_uuids:
            self._credentials.pop(child_uuid, None)

    def _now(self) -> int:
        """Return the current Unix time as an integer."""

        return int(self._clock())


child_credential_store = ChildCredentialStore()


def store_child_credentials(response: dict[str, Any]) -> dict[str, Any]:
    """Store child credentials and return non-secret metadata."""

    credential = child_credential_store.store(response)
    return credential.public_metadata()


def get_child_credentials(child_container_uuid: str) -> ChildCredential:
    """Return stored credentials for later Tenable MCP calls."""

    return child_credential_store.get(child_container_uuid)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    """Validate and normalize a required string."""

    if not isinstance(value, str) or not value.strip():
        raise ChildCredentialStoreError(
            f"{field_name} must be a non-empty string."
        )

    return value.strip()


def _parse_expiration(value: Any) -> int | None:
    """Parse an optional Unix expiration timestamp."""

    if value is None:
        return None

    if isinstance(value, bool):
        raise ChildCredentialStoreError(
            "keys_expiration_epoch_seconds must be an integer."
        )

    try:
        expiration = int(value)
    except (TypeError, ValueError) as exc:
        raise ChildCredentialStoreError(
            "keys_expiration_epoch_seconds must be an integer."
        ) from exc

    return expiration
