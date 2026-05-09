"""Single-child orchestration helpers for Tenable's hosted MCP server."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from tenable_mcp_mssp.child_account_eligibility import require_active_child_account
from tenable_mcp_mssp.child_credentials import (
    ChildCredential,
    get_or_generate_child_credentials,
)
from tenable_mcp_mssp.tenable_mcp_client import (
    call_tenable_mcp_tool,
    list_tenable_mcp_tools,
)


logger = logging.getLogger(__name__)


class TenableMcpRecipeError(ValueError):
    """Raised when a Tenable MCP recipe is invalid."""


async def list_available_tenable_mcp_tools(
    child_container_uuid: str,
    credential_provider: Callable[[str], ChildCredential] = (
        get_or_generate_child_credentials
    ),
    tool_lister: Callable[[str, str], Any] = list_tenable_mcp_tools,
    eligibility_checker: Callable[[str], object] = require_active_child_account,
) -> list[dict[str, Any]]:
    """List official Tenable MCP tools available to a child container."""

    logger.info(
        "Listing Tenable Hexa AI MCP tools for child %s.",
        child_container_uuid,
    )
    eligibility_checker(child_container_uuid)
    credential = credential_provider(child_container_uuid)
    try:
        tools = await tool_lister(
            credential.access_key,
            credential.secret_key,
        )
    except Exception:
        logger.warning(
            "Failed to list Tenable Hexa AI MCP tools for child %s.",
            child_container_uuid,
        )
        raise

    logger.info(
        "Listed %d Tenable Hexa AI MCP tools for child %s.",
        len(tools),
        child_container_uuid,
    )
    return tools


async def run_tenable_mcp_tool_for_child(
    child_container_uuid: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    credential_provider: Callable[[str], ChildCredential] = (
        get_or_generate_child_credentials
    ),
    tool_runner: Callable[[str, str, str, dict[str, Any] | None], Any] = (
        call_tenable_mcp_tool
    ),
    eligibility_checker: Callable[[str], object] = require_active_child_account,
) -> object:
    """Run an official Tenable MCP tool for a child container."""

    logger.info(
        "Calling Tenable Hexa AI MCP tool %s for child %s.",
        tool_name,
        child_container_uuid,
    )
    eligibility_checker(child_container_uuid)
    credential = credential_provider(child_container_uuid)
    try:
        result = await tool_runner(
            credential.access_key,
            credential.secret_key,
            tool_name,
            arguments,
        )
    except Exception:
        logger.warning(
            "Failed to call Tenable Hexa AI MCP tool %s for child %s.",
            tool_name,
            child_container_uuid,
        )
        raise

    logger.info(
        "Called Tenable Hexa AI MCP tool %s for child %s.",
        tool_name,
        child_container_uuid,
    )
    return result


async def run_tenable_mcp_recipe_for_child(
    child_container_uuid: str,
    recipe: list[dict[str, object]],
    step_runner: Callable[[str, dict[str, Any] | None], Any] | None = None,
    eligibility_checker: Callable[[str], object] = require_active_child_account,
) -> dict[str, object]:
    """Run a recipe of official Tenable MCP tools for a child container."""

    validated_recipe = _validate_recipe(recipe)
    logger.info(
        "Running Tenable Hexa AI MCP recipe with %d steps for child %s.",
        len(validated_recipe),
        child_container_uuid,
    )
    eligibility_checker(child_container_uuid)
    current_step_runner = step_runner or (
        lambda tool_name, arguments: run_tenable_mcp_tool_for_child(
            child_container_uuid,
            tool_name,
            arguments,
            eligibility_checker=lambda child_uuid: None,
        )
    )
    steps: list[dict[str, object]] = []

    for index, step in enumerate(validated_recipe):
        tool_name = step["tool_name"]
        arguments = step.get("arguments")

        try:
            result = await current_step_runner(tool_name, arguments)
        except Exception as exc:
            logger.warning(
                "Failed Tenable Hexa AI MCP recipe step %d tool %s for child %s.",
                index,
                tool_name,
                child_container_uuid,
            )
            steps.append(
                {
                    "index": index,
                    "tool_name": tool_name,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            return {
                "child_container_uuid": child_container_uuid,
                "status": "failed",
                "failed_step": index,
                "steps": steps,
            }

        logger.info(
            "Completed Tenable Hexa AI MCP recipe step %d tool %s for child %s.",
            index,
            tool_name,
            child_container_uuid,
        )
        steps.append(
            {
                "index": index,
                "tool_name": tool_name,
                "status": "succeeded",
                "result": result,
            }
        )

    logger.info(
        "Completed Tenable Hexa AI MCP recipe for child %s.",
        child_container_uuid,
    )
    return {
        "child_container_uuid": child_container_uuid,
        "status": "succeeded",
        "steps": steps,
    }


def _validate_recipe(recipe: Any) -> list[dict[str, Any]]:
    """Validate and normalize a Tenable MCP recipe."""

    if not isinstance(recipe, list) or not recipe:
        raise TenableMcpRecipeError("recipe must be a non-empty list.")

    validated_recipe: list[dict[str, Any]] = []

    for index, step in enumerate(recipe):
        if not isinstance(step, dict):
            raise TenableMcpRecipeError(
                f"recipe step {index} must be an object."
            )

        tool_name = step.get("tool_name")
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise TenableMcpRecipeError(
                f"recipe step {index} tool_name must be a non-empty string."
            )

        arguments = step.get("arguments")
        if arguments is not None and not isinstance(arguments, dict):
            raise TenableMcpRecipeError(
                f"recipe step {index} arguments must be a dictionary."
            )

        validated_recipe.append(
            {
                "tool_name": tool_name.strip(),
                "arguments": arguments,
            }
        )

    return validated_recipe
