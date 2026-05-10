"""Multi-child orchestration helpers for Tenable's hosted MCP server."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from tenable_mcp_mssp.child_fanout import (
    DEFAULT_CHILD_TIMEOUT_SECONDS,
    DEFAULT_MAX_CONCURRENCY,
    ChildFanoutError,
    ProgressReporter,
    run_child_fanout,
)
from tenable_mcp_mssp.mssp_accounts import list_child_accounts
from tenable_mcp_mssp.single_child_tenable_mcp import run_tenable_mcp_recipe_for_child


class MultiChildRecipeError(ValueError):
    """Raised when multi-child recipe execution input is invalid."""


async def run_tenable_mcp_recipe_across_child_containers(
    child_container_uuids: list[str],
    recipe: list[dict[str, object]],
    required_license: str | None = None,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    child_timeout_seconds: int | None = DEFAULT_CHILD_TIMEOUT_SECONDS,
    recipe_runner: Callable[
        [str, list[dict[str, object]]],
        Awaitable[dict[str, object]],
    ] = run_tenable_mcp_recipe_for_child,
    account_lister: Callable[[], list[dict[str, Any]]] = list_child_accounts,
    progress_reporter: ProgressReporter | None = None,
) -> dict[str, object]:
    """Run a Tenable MCP recipe across multiple child containers."""

    async def child_worker(
        child_container_uuid: str,
        account: object,
    ) -> dict[str, object]:
        return await recipe_runner(child_container_uuid, recipe)

    try:
        return await run_child_fanout(
            child_container_uuids,
            child_worker,
            required_license=required_license,
            max_concurrency=max_concurrency,
            child_timeout_seconds=child_timeout_seconds,
            account_lister=account_lister,
            progress_reporter=progress_reporter,
            operation_name="recipe",
            timeout_error_label="child recipe",
        )
    except ChildFanoutError as exc:
        raise MultiChildRecipeError(str(exc)) from exc
