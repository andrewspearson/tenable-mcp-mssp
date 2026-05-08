"""Eligibility checks for actions against MSSP child accounts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from tenable_mcp_mssp.account_capabilities import (
    get_license_expiration_epoch,
    is_license_expired,
)
from tenable_mcp_mssp.mssp_accounts import list_child_accounts


class ChildAccountEligibilityError(RuntimeError):
    """Raised when a child account is not eligible for action."""


def build_child_account_lookup(
    account_lister: Callable[[], list[dict[str, Any]]] = list_child_accounts,
) -> dict[str, dict[str, Any]]:
    """Build a child account lookup keyed by child account UUID."""

    return {
        account["uuid"]: account
        for account in account_lister()
        if isinstance(account.get("uuid"), str)
    }


def require_active_child_account(
    child_container_uuid: str,
    account_lister: Callable[[], list[dict[str, Any]]] = list_child_accounts,
) -> dict[str, Any]:
    """Return the active child account or raise a clear eligibility error."""

    account_lookup = build_child_account_lookup(account_lister)
    reason = child_account_ineligible_reason(child_container_uuid, account_lookup)
    if reason is not None:
        raise ChildAccountEligibilityError(reason)

    return account_lookup[child_container_uuid]


def child_account_ineligible_reason(
    child_container_uuid: str,
    account_lookup: Mapping[str, Mapping[str, Any]],
) -> str | None:
    """Return why a child account is ineligible, or None when active."""

    account = account_lookup.get(child_container_uuid)
    if account is None:
        return "child account not found for active license check"

    expiration = get_license_expiration_epoch(account)
    if expiration is None:
        return "child account license expiration date is missing or invalid"

    if is_license_expired(account):
        return "child account license is expired"

    return None
