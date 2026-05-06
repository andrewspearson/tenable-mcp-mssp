"""MSSP child account listing logic."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from tenable.io import TenableIO

from simple_mcp.tenable_client import create_tenable_client


ACCOUNT_LIST_PATH = "mssp/accounts"
ACCOUNT_LIST_HEADERS = {"Content-Type": "application/json"}


@dataclass(frozen=True, slots=True)
class ChildAccount:
    """A Tenable MSSP child account."""

    name: str
    uuid: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable representation of the account."""

        return asdict(self)


class AccountListingError(RuntimeError):
    """Raised when child accounts cannot be retrieved or parsed."""


def list_child_accounts(client: TenableIO | None = None) -> list[ChildAccount]:
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


def list_child_accounts_as_dicts(
    client: TenableIO | None = None,
) -> list[dict[str, str]]:
    """List child accounts as JSON-serializable dictionaries."""

    return [account.to_dict() for account in list_child_accounts(client)]


def parse_child_accounts(payload: Any) -> list[ChildAccount]:
    """Parse a Tenable MSSP account list response."""

    if not isinstance(payload, dict):
        raise AccountListingError("Invalid account response: expected an object.")

    accounts = payload.get("accounts")
    if not isinstance(accounts, list):
        raise AccountListingError("Invalid account response: missing accounts list.")

    return [_parse_child_account(account) for account in accounts]


def _parse_child_account(account: Any) -> ChildAccount:
    """Parse one child account from the Tenable response."""

    if not isinstance(account, dict):
        raise AccountListingError("Invalid account entry: expected an object.")

    account_uuid = account.get("uuid")
    account_name = account.get("container_name")

    if not isinstance(account_uuid, str) or not account_uuid.strip():
        raise AccountListingError("Invalid account entry: missing uuid.")

    if not isinstance(account_name, str) or not account_name.strip():
        raise AccountListingError("Invalid account entry: missing container_name.")

    return ChildAccount(name=account_name, uuid=account_uuid)
