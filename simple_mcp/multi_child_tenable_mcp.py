"""Multi-child orchestration helpers for Tenable's hosted MCP server."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from simple_mcp.account_capabilities import (
    has_license,
    supports_tenable_one_inventory,
    supports_vulnerability_management,
)
from simple_mcp.mssp_accounts import list_child_accounts
from simple_mcp.single_child_tenable_mcp import run_tenable_mcp_recipe_for_child


DEFAULT_MAX_CONCURRENCY = 10
VULNERABILITY_MANAGEMENT_ALIAS = "vulnerability_management"
TENABLE_ONE_INVENTORY_ALIAS = "tenable_one_inventory"


class MultiChildRecipeError(ValueError):
    """Raised when multi-child recipe execution input is invalid."""


async def run_tenable_mcp_recipe_across_child_containers(
    child_container_uuids: list[str],
    recipe: list[dict[str, object]],
    required_license: str | None = None,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    recipe_runner: Callable[
        [str, list[dict[str, object]]],
        Awaitable[dict[str, object]],
    ] = run_tenable_mcp_recipe_for_child,
    account_lister: Callable[[], list[dict[str, Any]]] = list_child_accounts,
) -> dict[str, object]:
    """Run a Tenable MCP recipe across multiple child containers."""

    validated_child_uuids = _validate_child_container_uuids(child_container_uuids)
    validated_max_concurrency = _validate_max_concurrency(max_concurrency)
    license_requirement = _normalize_required_license(required_license)
    account_lookup = (
        _build_account_lookup(account_lister) if license_requirement else {}
    )
    semaphore = asyncio.Semaphore(validated_max_concurrency)

    async def run_one(child_container_uuid: str) -> dict[str, object]:
        if license_requirement:
            skip_reason = _license_skip_reason(
                child_container_uuid,
                account_lookup,
                license_requirement,
            )
            if skip_reason:
                return {
                    "child_container_uuid": child_container_uuid,
                    "status": "skipped",
                    "reason": skip_reason,
                }

        async with semaphore:
            try:
                result = await recipe_runner(child_container_uuid, recipe)
            except Exception as exc:
                return {
                    "child_container_uuid": child_container_uuid,
                    "status": "failed",
                    "error": str(exc),
                }

        if not isinstance(result, dict):
            return {
                "child_container_uuid": child_container_uuid,
                "status": "failed",
                "error": "Recipe runner returned an invalid report.",
            }

        status = result.get("status")
        if status not in {"succeeded", "failed"}:
            return {
                "child_container_uuid": child_container_uuid,
                "status": "failed",
                "error": "Recipe runner returned an invalid status.",
            }

        return {
            "child_container_uuid": child_container_uuid,
            "status": status,
            "result": result,
        }

    children = await asyncio.gather(
        *(run_one(child_uuid) for child_uuid in validated_child_uuids)
    )

    return {
        "queued": len(validated_child_uuids),
        "succeeded": _count_status(children, "succeeded"),
        "failed": _count_status(children, "failed"),
        "skipped": _count_status(children, "skipped"),
        "children": children,
    }


def _validate_child_container_uuids(child_container_uuids: Any) -> list[str]:
    """Validate and normalize child container UUID input."""

    if not isinstance(child_container_uuids, list) or not child_container_uuids:
        raise MultiChildRecipeError(
            "child_container_uuids must be a non-empty list."
        )

    validated_child_uuids: list[str] = []
    for index, child_uuid in enumerate(child_container_uuids):
        if not isinstance(child_uuid, str) or not child_uuid.strip():
            raise MultiChildRecipeError(
                f"child_container_uuids item {index} must be a non-empty string."
            )
        validated_child_uuids.append(child_uuid.strip())

    return validated_child_uuids


def _validate_max_concurrency(max_concurrency: Any) -> int:
    """Validate max concurrency input."""

    if not isinstance(max_concurrency, int) or max_concurrency < 1:
        raise MultiChildRecipeError("max_concurrency must be a positive integer.")

    return max_concurrency


def _normalize_required_license(required_license: str | None) -> str | None:
    """Normalize the optional license/capability gate."""

    if required_license is None:
        return None

    if not isinstance(required_license, str) or not required_license.strip():
        raise MultiChildRecipeError(
            "required_license must be a non-empty string when provided."
        )

    return required_license.strip().casefold()


def _build_account_lookup(
    account_lister: Callable[[], list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Build a child account lookup keyed by account UUID."""

    return {
        account["uuid"]: account
        for account in account_lister()
        if isinstance(account.get("uuid"), str)
    }


def _license_skip_reason(
    child_container_uuid: str,
    account_lookup: Mapping[str, Mapping[str, Any]],
    required_license: str,
) -> str | None:
    """Return a skip reason when a child does not meet a license gate."""

    account = account_lookup.get(child_container_uuid)
    if account is None:
        return "child account not found for required license check"

    if _account_has_required_license(account, required_license):
        return None

    return f"missing required license: {required_license}"


def _account_has_required_license(
    account: Mapping[str, Any],
    required_license: str,
) -> bool:
    """Return whether an account satisfies the license/capability gate."""

    if required_license == VULNERABILITY_MANAGEMENT_ALIAS:
        return supports_vulnerability_management(account)

    if required_license == TENABLE_ONE_INVENTORY_ALIAS:
        return supports_tenable_one_inventory(account)

    return has_license(account, required_license)


def _count_status(children: list[dict[str, object]], status: str) -> int:
    """Count child reports with the requested status."""

    return sum(child.get("status") == status for child in children)
