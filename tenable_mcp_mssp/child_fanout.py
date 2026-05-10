"""Shared async fan-out for child-container work."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from tenable_mcp_mssp.account_capabilities import (
    has_license,
    supports_tenable_one_inventory,
    supports_vulnerability_management,
)
from tenable_mcp_mssp.child_account_eligibility import (
    build_child_account_lookup,
    child_account_ineligible_reason,
)
from tenable_mcp_mssp.mssp_accounts import list_child_accounts


DEFAULT_MAX_CONCURRENCY = 10
DEFAULT_CHILD_TIMEOUT_SECONDS = 300
VULNERABILITY_MANAGEMENT_ALIAS = "vulnerability_management"
TENABLE_ONE_INVENTORY_ALIAS = "tenable_one_inventory"
ProgressReporter = Callable[[int, int, str], Awaitable[None]]
ChildWorker = Callable[[str, Mapping[str, Any]], Awaitable[dict[str, object]]]
logger = logging.getLogger(__name__)


class ChildFanoutError(ValueError):
    """Raised when child fan-out input is invalid."""


async def run_child_fanout(
    child_container_uuids: list[str],
    child_worker: ChildWorker,
    required_license: str | None = None,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    child_timeout_seconds: int | None = DEFAULT_CHILD_TIMEOUT_SECONDS,
    account_lister: Callable[[], list[dict[str, Any]]] = list_child_accounts,
    progress_reporter: ProgressReporter | None = None,
    operation_name: str = "child work",
    timeout_error_label: str = "child work",
    allow_empty: bool = False,
) -> dict[str, object]:
    """Run child work across containers with common fan-out controls."""

    validated_child_uuids = validate_child_container_uuids(
        child_container_uuids,
        allow_empty=allow_empty,
    )
    validated_max_concurrency = validate_max_concurrency(max_concurrency)
    validated_child_timeout = validate_child_timeout(child_timeout_seconds)
    license_requirement = normalize_required_license(required_license)
    account_lookup = build_child_account_lookup(account_lister)
    semaphore = asyncio.Semaphore(validated_max_concurrency)
    total_children = len(validated_child_uuids)
    completed_children = 0
    progress_lock = asyncio.Lock()

    async def report_progress(done: int, message: str) -> None:
        if progress_reporter is not None:
            await progress_reporter(done, total_children, message)

    async def mark_child_done(message: str) -> None:
        nonlocal completed_children
        async with progress_lock:
            completed_children += 1
            done = completed_children

        await report_progress(done, message)

    await report_progress(
        0,
        f"Batch started: {total_children} requested child containers.",
    )
    logger.info(
        "Started %s batch for %d requested children.",
        operation_name,
        total_children,
    )

    async def run_one(child_container_uuid: str) -> dict[str, object]:
        active_skip_reason = child_account_ineligible_reason(
            child_container_uuid,
            account_lookup,
        )
        if active_skip_reason:
            return await _skip_child(
                child_container_uuid,
                active_skip_reason,
                operation_name,
                mark_child_done,
            )

        if license_requirement:
            skip_reason = license_skip_reason(
                child_container_uuid,
                account_lookup,
                license_requirement,
            )
            if skip_reason:
                return await _skip_child(
                    child_container_uuid,
                    skip_reason,
                    operation_name,
                    mark_child_done,
                )

        account = account_lookup[child_container_uuid]
        async with semaphore:
            logger.info(
                "Running %s for child %s.",
                operation_name,
                child_container_uuid,
            )
            await report_progress(
                completed_children,
                f"Batch running: child {child_container_uuid}.",
            )
            try:
                result = await run_child_with_timeout(
                    child_worker(child_container_uuid, account),
                    validated_child_timeout,
                )
            except TimeoutError:
                logger.warning(
                    "Timed out %s for child %s after %s seconds.",
                    operation_name,
                    child_container_uuid,
                    validated_child_timeout,
                )
                await mark_child_done(
                    f"Batch completed child {child_container_uuid}: failed."
                )
                return {
                    "child_container_uuid": child_container_uuid,
                    "status": "failed",
                    "error": (
                        f"{timeout_error_label} timed out after "
                        f"{validated_child_timeout} seconds"
                    ),
                }
            except Exception as exc:
                logger.warning(
                    "Failed %s for child %s.",
                    operation_name,
                    child_container_uuid,
                )
                await mark_child_done(
                    f"Batch completed child {child_container_uuid}: failed."
                )
                return {
                    "child_container_uuid": child_container_uuid,
                    "status": "failed",
                    "error": str(exc),
                }

        if not isinstance(result, dict):
            logger.warning(
                "%s for child %s returned an invalid report.",
                operation_name,
                child_container_uuid,
            )
            await mark_child_done(
                f"Batch completed child {child_container_uuid}: failed."
            )
            return {
                "child_container_uuid": child_container_uuid,
                "status": "failed",
                "error": "Child worker returned an invalid report.",
            }

        status = result.get("status")
        if status not in {"succeeded", "failed"}:
            logger.warning(
                "%s for child %s returned an invalid status.",
                operation_name,
                child_container_uuid,
            )
            await mark_child_done(
                f"Batch completed child {child_container_uuid}: failed."
            )
            return {
                "child_container_uuid": child_container_uuid,
                "status": "failed",
                "error": "Child worker returned an invalid status.",
            }

        logger.info(
            "Completed %s for child %s with status %s.",
            operation_name,
            child_container_uuid,
            status,
        )
        await mark_child_done(
            f"Batch completed child {child_container_uuid}: {status}."
        )
        return {
            "child_container_uuid": child_container_uuid,
            "status": status,
            "result": result,
        }

    children = await asyncio.gather(
        *(run_one(child_uuid) for child_uuid in validated_child_uuids)
    )
    succeeded = count_status(children, "succeeded")
    failed = count_status(children, "failed")
    skipped = count_status(children, "skipped")
    await report_progress(
        total_children,
        (
            "Batch complete: "
            f"{succeeded} succeeded, {failed} failed, {skipped} skipped."
        ),
    )
    logger.info(
        "Completed %s batch: %d succeeded, %d failed, %d skipped.",
        operation_name,
        succeeded,
        failed,
        skipped,
    )

    return {
        "queued": len(validated_child_uuids),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "children": children,
    }


def validate_child_container_uuids(
    child_container_uuids: Any,
    allow_empty: bool = False,
) -> list[str]:
    """Validate and normalize child container UUID input."""

    if not isinstance(child_container_uuids, list):
        raise ChildFanoutError("child_container_uuids must be a list.")

    if not child_container_uuids and not allow_empty:
        raise ChildFanoutError(
            "child_container_uuids must be a non-empty list."
        )

    validated_child_uuids: list[str] = []
    for index, child_uuid in enumerate(child_container_uuids):
        if not isinstance(child_uuid, str) or not child_uuid.strip():
            raise ChildFanoutError(
                f"child_container_uuids item {index} must be a non-empty string."
            )
        validated_child_uuids.append(child_uuid.strip())

    return validated_child_uuids


def validate_max_concurrency(max_concurrency: Any) -> int:
    """Validate max concurrency input."""

    if not isinstance(max_concurrency, int) or max_concurrency < 1:
        raise ChildFanoutError("max_concurrency must be a positive integer.")

    return max_concurrency


def validate_child_timeout(child_timeout_seconds: Any) -> int | None:
    """Validate per-child timeout input."""

    if child_timeout_seconds is None:
        return None

    if (
        not isinstance(child_timeout_seconds, int)
        or isinstance(child_timeout_seconds, bool)
        or child_timeout_seconds < 1
    ):
        raise ChildFanoutError(
            "child_timeout_seconds must be a positive integer or None."
        )

    return child_timeout_seconds


async def run_child_with_timeout(
    child_run: Awaitable[dict[str, object]],
    child_timeout_seconds: int | None,
) -> dict[str, object]:
    """Run one child operation with an optional timeout."""

    if child_timeout_seconds is None:
        return await child_run

    return await asyncio.wait_for(child_run, timeout=child_timeout_seconds)


def normalize_required_license(required_license: str | None) -> str | None:
    """Normalize the optional license/capability gate."""

    if required_license is None:
        return None

    if not isinstance(required_license, str) or not required_license.strip():
        raise ChildFanoutError(
            "required_license must be a non-empty string when provided."
        )

    return required_license.strip().casefold()


def license_skip_reason(
    child_container_uuid: str,
    account_lookup: Mapping[str, Mapping[str, Any]],
    required_license: str,
) -> str | None:
    """Return a skip reason when a child does not meet a license gate."""

    account = account_lookup.get(child_container_uuid)
    if account is None:
        return "child account not found for required license check"

    if account_has_required_license(account, required_license):
        return None

    return f"missing required license: {required_license}"


def account_has_required_license(
    account: Mapping[str, Any],
    required_license: str,
) -> bool:
    """Return whether an account satisfies the license/capability gate."""

    if required_license == VULNERABILITY_MANAGEMENT_ALIAS:
        return supports_vulnerability_management(account)

    if required_license == TENABLE_ONE_INVENTORY_ALIAS:
        return supports_tenable_one_inventory(account)

    return has_license(account, required_license)


def count_status(children: list[dict[str, object]], status: str) -> int:
    """Count child reports with the requested status."""

    return sum(child.get("status") == status for child in children)


async def _skip_child(
    child_container_uuid: str,
    reason: str,
    operation_name: str,
    mark_child_done: Callable[[str], Awaitable[None]],
) -> dict[str, object]:
    """Return a skipped child report and publish progress."""

    logger.info(
        "Skipped child %s before %s: %s.",
        child_container_uuid,
        operation_name,
        reason,
    )
    await mark_child_done(
        f"Batch skipped: child {child_container_uuid}: {reason}."
    )
    return {
        "child_container_uuid": child_container_uuid,
        "status": "skipped",
        "reason": reason,
    }
