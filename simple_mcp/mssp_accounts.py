"""MSSP child account listing logic."""

from __future__ import annotations

from typing import Any

from tenable.io import TenableIO

from simple_mcp.tenable_client import create_tenable_client


ACCOUNT_LIST_PATH = "mssp/accounts"
ACCOUNT_LIST_HEADERS = {"Content-Type": "application/json"}


class AccountListingError(RuntimeError):
    """Raised when child accounts cannot be retrieved or parsed."""


def list_child_accounts(client: TenableIO | None = None) -> list[dict[str, Any]]:
    """List child accounts connected to the Tenable MSSP Portal."""

    current_client = client or create_tenable_client()

    try:
        response = current_client.get(
            ACCOUNT_LIST_PATH,
            headers=ACCOUNT_LIST_HEADERS,
        )
        payload = response.json()
    except Exception as exc:
        raise AccountListingError("Failed to retrieve MSSP child accounts.") from exc

    return parse_child_accounts(payload)


def parse_child_accounts(payload: Any) -> list[dict[str, Any]]:
    """Parse a Tenable MSSP account list response."""

    if not isinstance(payload, dict):
        raise AccountListingError("Invalid account response: expected an object.")

    accounts = payload.get("accounts")
    if not isinstance(accounts, list):
        raise AccountListingError("Invalid account response: missing accounts list.")

    return [_parse_child_account(account) for account in accounts]


def _parse_child_account(account: Any) -> dict[str, Any]:
    """Parse one child account from the Tenable response."""

    if not isinstance(account, dict):
        raise AccountListingError("Invalid account entry: expected an object.")

    return account
