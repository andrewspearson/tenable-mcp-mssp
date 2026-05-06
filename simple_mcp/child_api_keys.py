"""MSSP child API key generation logic."""

from __future__ import annotations

from typing import Any

from tenable.io import TenableIO

from simple_mcp.tenable_client import create_tenable_client


CHILD_KEYS_PATH = "mssp/accounts/mssp-child-keys"
CHILD_KEYS_HEADERS = {"Content-Type": "application/json"}
MAX_KEYS_VALIDITY_SECONDS = 3600


class ChildApiKeyGenerationError(RuntimeError):
    """Raised when child API keys cannot be generated or parsed."""


def generate_child_api_keys(
    child_container_uuid: str,
    keys_validity_duration_seconds: int | None = None,
    client: TenableIO | None = None,
) -> dict[str, Any]:
    """Generate temporary API keys for a Tenable MSSP child container."""

    request_body = build_child_key_request_body(
        child_container_uuid,
        keys_validity_duration_seconds,
    )
    current_client = client or create_tenable_client()

    try:
        response = current_client.post(
            CHILD_KEYS_PATH,
            json=request_body,
            headers=CHILD_KEYS_HEADERS,
        )
        payload = response.json() if hasattr(response, "json") else response
    except Exception as exc:
        raise ChildApiKeyGenerationError(
            "Failed to generate child API keys."
        ) from exc

    return parse_child_api_key_response(payload)


def build_child_key_request_body(
    child_container_uuid: str,
    keys_validity_duration_seconds: int | None = None,
) -> dict[str, Any]:
    """Build and validate a child API key generation request body."""

    if not isinstance(child_container_uuid, str) or not child_container_uuid.strip():
        raise ChildApiKeyGenerationError(
            "child_container_uuid must be a non-empty string."
        )

    request_body: dict[str, Any] = {
        "child_container_uuid": child_container_uuid.strip(),
    }

    if keys_validity_duration_seconds is None:
        return request_body

    if (
        not isinstance(keys_validity_duration_seconds, int)
        or isinstance(keys_validity_duration_seconds, bool)
    ):
        raise ChildApiKeyGenerationError(
            "keys_validity_duration_seconds must be an integer."
        )

    if not 1 <= keys_validity_duration_seconds <= MAX_KEYS_VALIDITY_SECONDS:
        raise ChildApiKeyGenerationError(
            "keys_validity_duration_seconds must be between 1 and 3600."
        )

    request_body["keys_validity_duration_seconds"] = (
        keys_validity_duration_seconds
    )
    return request_body


def parse_child_api_key_response(payload: Any) -> dict[str, Any]:
    """Parse a Tenable child API key generation response."""

    if not isinstance(payload, dict):
        raise ChildApiKeyGenerationError(
            "Invalid child API key response: expected an object."
        )

    return payload
