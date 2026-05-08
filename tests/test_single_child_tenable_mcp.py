"""Tests for single-child Tenable MCP orchestration."""

from __future__ import annotations

import unittest

from simple_mcp.child_account_eligibility import ChildAccountEligibilityError
from simple_mcp.child_credentials import ChildCredential
from simple_mcp.single_child_tenable_mcp import (
    TenableMcpRecipeError,
    list_available_tenable_mcp_tools,
    run_tenable_mcp_recipe_for_child,
    run_tenable_mcp_tool_for_child,
)


def raise_expired_child(child_uuid: str) -> None:
    """Raise an expired-child eligibility error for tests."""

    raise ChildAccountEligibilityError("child account license is expired")


class SingleChildTenableMcpTests(unittest.IsolatedAsyncioTestCase):
    """Tests for single-child Tenable MCP orchestration helpers."""

    async def test_list_available_tenable_mcp_tools_uses_credentials(self) -> None:
        """Tool listing should call the official MCP lister with stored keys."""

        credential = ChildCredential(
            child_container_uuid="child-uuid",
            access_key="stored-access-key",
            secret_key="stored-secret-key",
        )
        tool_result = [
            {
                "name": "scan_list",
                "description": "List scans.",
                "input_schema": {"type": "object"},
            }
        ]
        calls: list[tuple[str, str]] = []

        async def fake_tool_lister(
            access_key: str,
            secret_key: str,
        ) -> list[dict[str, object]]:
            calls.append((access_key, secret_key))
            return tool_result

        result = await list_available_tenable_mcp_tools(
            "child-uuid",
            credential_provider=lambda child_uuid: credential,
            tool_lister=fake_tool_lister,
            eligibility_checker=lambda child_uuid: None,
        )

        self.assertEqual(result, tool_result)
        self.assertEqual(calls, [("stored-access-key", "stored-secret-key")])

    async def test_list_available_tenable_mcp_tools_does_not_return_keys(
        self,
    ) -> None:
        """Public orchestration output should not include generated keys."""

        credential = ChildCredential(
            child_container_uuid="child-uuid",
            access_key="stored-access-key",
            secret_key="stored-secret-key",
        )

        async def fake_tool_lister(
            access_key: str,
            secret_key: str,
        ) -> list[dict[str, object]]:
            return [
                {
                    "name": "scan_list",
                    "description": "List scans.",
                    "input_schema": {"type": "object"},
                }
            ]

        result = await list_available_tenable_mcp_tools(
            "child-uuid",
            credential_provider=lambda child_uuid: credential,
            tool_lister=fake_tool_lister,
            eligibility_checker=lambda child_uuid: None,
        )

        self.assertNotIn("access_key", result[0])
        self.assertNotIn("secret_key", result[0])

    async def test_run_tenable_mcp_tool_for_child_forwards_call_inputs(
        self,
    ) -> None:
        """Tool runner should receive child keys, tool name, and arguments."""

        credential = ChildCredential(
            child_container_uuid="child-uuid",
            access_key="stored-access-key",
            secret_key="stored-secret-key",
        )
        arguments = {"plugin_id": "12345"}
        tool_result = {"status": "ok", "items": [{"id": 1}]}
        calls: list[
            tuple[str, str, str, dict[str, object] | None]
        ] = []

        async def fake_tool_runner(
            access_key: str,
            secret_key: str,
            tool_name: str,
            tool_arguments: dict[str, object] | None = None,
        ) -> object:
            calls.append(
                (access_key, secret_key, tool_name, tool_arguments)
            )
            return tool_result

        result = await run_tenable_mcp_tool_for_child(
            "child-uuid",
            "vulnerability_findings",
            arguments,
            credential_provider=lambda child_uuid: credential,
            tool_runner=fake_tool_runner,
            eligibility_checker=lambda child_uuid: None,
        )

        self.assertIs(result, tool_result)
        self.assertEqual(
            calls,
            [
                (
                    "stored-access-key",
                    "stored-secret-key",
                    "vulnerability_findings",
                    arguments,
                )
            ],
        )

    async def test_run_tenable_mcp_tool_for_child_handles_none_arguments(
        self,
    ) -> None:
        """None arguments should be forwarded to the lower-level helper."""

        credential = ChildCredential(
            child_container_uuid="child-uuid",
            access_key="stored-access-key",
            secret_key="stored-secret-key",
        )
        calls: list[
            tuple[str, str, str, dict[str, object] | None]
        ] = []

        async def fake_tool_runner(
            access_key: str,
            secret_key: str,
            tool_name: str,
            tool_arguments: dict[str, object] | None = None,
        ) -> object:
            calls.append(
                (access_key, secret_key, tool_name, tool_arguments)
            )
            return ["official-result"]

        result = await run_tenable_mcp_tool_for_child(
            "child-uuid",
            "asset_list",
            credential_provider=lambda child_uuid: credential,
            tool_runner=fake_tool_runner,
            eligibility_checker=lambda child_uuid: None,
        )

        self.assertEqual(result, ["official-result"])
        self.assertEqual(
            calls,
            [
                (
                    "stored-access-key",
                    "stored-secret-key",
                    "asset_list",
                    None,
                )
            ],
        )

    async def test_run_tenable_mcp_recipe_for_child_validates_shape(
        self,
    ) -> None:
        """Recipe validation should reject invalid shapes before execution."""

        invalid_recipes = [
            ([], "non-empty list"),
            ("not-a-list", "non-empty list"),
            ([["not-an-object"]], "step 0 must be an object"),
            ([{}], "step 0 tool_name must be a non-empty string"),
            ([{"tool_name": "   "}], "step 0 tool_name"),
            ([{"tool_name": "asset_list", "arguments": []}], "arguments"),
        ]

        async def fail_if_called(
            tool_name: str,
            arguments: dict[str, object] | None = None,
        ) -> object:
            raise AssertionError("step runner should not be called")

        for recipe, expected_message in invalid_recipes:
            with self.subTest(recipe=recipe):
                with self.assertRaisesRegex(
                    TenableMcpRecipeError,
                    expected_message,
                ):
                    await run_tenable_mcp_recipe_for_child(
                        "child-uuid",
                        recipe,  # type: ignore[arg-type]
                        step_runner=fail_if_called,
                        eligibility_checker=lambda child_uuid: None,
                    )

    async def test_run_tenable_mcp_recipe_for_child_runs_steps_in_order(
        self,
    ) -> None:
        """Recipe steps should execute sequentially and preserve results."""

        calls: list[tuple[str, dict[str, object] | None]] = []

        async def fake_step_runner(
            tool_name: str,
            arguments: dict[str, object] | None = None,
        ) -> object:
            calls.append((tool_name, arguments))
            return {"tool": tool_name, "arguments": arguments}

        result = await run_tenable_mcp_recipe_for_child(
            "child-uuid",
            [
                {"tool_name": "asset_list"},
                {"tool_name": "finding_search", "arguments": {"severity": "high"}},
            ],
            step_runner=fake_step_runner,
            eligibility_checker=lambda child_uuid: None,
        )

        self.assertEqual(
            calls,
            [
                ("asset_list", None),
                ("finding_search", {"severity": "high"}),
            ],
        )
        self.assertEqual(
            result,
            {
                "child_container_uuid": "child-uuid",
                "status": "succeeded",
                "steps": [
                    {
                        "index": 0,
                        "tool_name": "asset_list",
                        "status": "succeeded",
                        "result": {"tool": "asset_list", "arguments": None},
                    },
                    {
                        "index": 1,
                        "tool_name": "finding_search",
                        "status": "succeeded",
                        "result": {
                            "tool": "finding_search",
                            "arguments": {"severity": "high"},
                        },
                    },
                ],
            },
        )

    async def test_run_tenable_mcp_recipe_for_child_stops_on_failure(
        self,
    ) -> None:
        """Recipe execution should stop on the first failed step."""

        calls: list[tuple[str, dict[str, object] | None]] = []

        async def fake_step_runner(
            tool_name: str,
            arguments: dict[str, object] | None = None,
        ) -> object:
            calls.append((tool_name, arguments))
            if tool_name == "failing_tool":
                raise RuntimeError("official MCP call failed")
            return {"tool": tool_name}

        result = await run_tenable_mcp_recipe_for_child(
            "child-uuid",
            [
                {"tool_name": "first_tool"},
                {"tool_name": "failing_tool", "arguments": {"limit": 10}},
                {"tool_name": "never_called"},
            ],
            step_runner=fake_step_runner,
            eligibility_checker=lambda child_uuid: None,
        )

        self.assertEqual(
            calls,
            [
                ("first_tool", None),
                ("failing_tool", {"limit": 10}),
            ],
        )
        self.assertEqual(
            result,
            {
                "child_container_uuid": "child-uuid",
                "status": "failed",
                "failed_step": 1,
                "steps": [
                    {
                        "index": 0,
                        "tool_name": "first_tool",
                        "status": "succeeded",
                        "result": {"tool": "first_tool"},
                    },
                    {
                        "index": 1,
                        "tool_name": "failing_tool",
                        "status": "failed",
                        "error": "official MCP call failed",
                    },
                ],
            },
        )

    async def test_list_available_tenable_mcp_tools_blocks_ineligible_child(
        self,
    ) -> None:
        """Ineligible children should be rejected before credentials are used."""

        def fail_credential_provider(child_uuid: str) -> ChildCredential:
            raise AssertionError("credential provider should not be called")

        async def fail_tool_lister(
            access_key: str,
            secret_key: str,
        ) -> list[dict[str, object]]:
            raise AssertionError("tool lister should not be called")

        with self.assertRaisesRegex(
            ChildAccountEligibilityError,
            "license is expired",
        ):
            await list_available_tenable_mcp_tools(
                "child-uuid",
                credential_provider=fail_credential_provider,
                tool_lister=fail_tool_lister,
                eligibility_checker=raise_expired_child,
            )

    async def test_run_tenable_mcp_tool_for_child_blocks_ineligible_child(
        self,
    ) -> None:
        """Ineligible children should be rejected before tool execution."""

        def fail_credential_provider(child_uuid: str) -> ChildCredential:
            raise AssertionError("credential provider should not be called")

        async def fail_tool_runner(
            access_key: str,
            secret_key: str,
            tool_name: str,
            arguments: dict[str, object] | None = None,
        ) -> object:
            raise AssertionError("tool runner should not be called")

        with self.assertRaisesRegex(
            ChildAccountEligibilityError,
            "license is expired",
        ):
            await run_tenable_mcp_tool_for_child(
                "child-uuid",
                "asset_list",
                credential_provider=fail_credential_provider,
                tool_runner=fail_tool_runner,
                eligibility_checker=raise_expired_child,
            )

    async def test_run_tenable_mcp_recipe_for_child_blocks_ineligible_child(
        self,
    ) -> None:
        """Ineligible children should be rejected before recipe steps run."""

        async def fail_step_runner(
            tool_name: str,
            arguments: dict[str, object] | None = None,
        ) -> object:
            raise AssertionError("step runner should not be called")

        with self.assertRaisesRegex(
            ChildAccountEligibilityError,
            "license is expired",
        ):
            await run_tenable_mcp_recipe_for_child(
                "child-uuid",
                [{"tool_name": "asset_list"}],
                step_runner=fail_step_runner,
                eligibility_checker=raise_expired_child,
            )


if __name__ == "__main__":
    unittest.main()
