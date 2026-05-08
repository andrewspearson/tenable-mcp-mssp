"""Tests for multi-child Tenable MCP orchestration."""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from simple_mcp.multi_child_tenable_mcp import (
    MultiChildRecipeError,
    run_tenable_mcp_recipe_across_child_containers,
)


class MultiChildTenableMcpTests(unittest.IsolatedAsyncioTestCase):
    """Tests for multi-child recipe fan-out helpers."""

    async def test_successful_children_produce_recipe_reports(self) -> None:
        """Successful child runs should be counted and reported."""

        recipe = [{"tool_name": "asset_list"}]

        async def fake_recipe_runner(
            child_uuid: str,
            recipe_input: list[dict[str, object]],
        ) -> dict[str, object]:
            return {
                "child_container_uuid": child_uuid,
                "status": "succeeded",
                "steps": [
                    {
                        "index": 0,
                        "tool_name": recipe_input[0]["tool_name"],
                        "status": "succeeded",
                        "result": {"child": child_uuid},
                    }
                ],
            }

        result = await run_tenable_mcp_recipe_across_child_containers(
            ["child-1", "child-2"],
            recipe,
            recipe_runner=fake_recipe_runner,
        )

        self.assertEqual(result["queued"], 2)
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(
            [child["status"] for child in result["children"]],
            ["succeeded", "succeeded"],
        )

    async def test_failed_child_does_not_stop_other_children(self) -> None:
        """One child-level failure should not stop the full fan-out."""

        calls: list[str] = []

        async def fake_recipe_runner(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            calls.append(child_uuid)
            if child_uuid == "child-2":
                raise RuntimeError("child run failed")
            return {
                "child_container_uuid": child_uuid,
                "status": "succeeded",
                "steps": [],
            }

        result = await run_tenable_mcp_recipe_across_child_containers(
            ["child-1", "child-2", "child-3"],
            [{"tool_name": "asset_list"}],
            recipe_runner=fake_recipe_runner,
        )

        self.assertEqual(calls, ["child-1", "child-2", "child-3"])
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["children"][1]["status"], "failed")
        self.assertEqual(result["children"][1]["error"], "child run failed")

    async def test_recipe_failed_report_is_preserved(self) -> None:
        """Recipe-level failed reports should be preserved under result."""

        async def fake_recipe_runner(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            return {
                "child_container_uuid": child_uuid,
                "status": "failed",
                "failed_step": 0,
                "steps": [
                    {
                        "index": 0,
                        "tool_name": "asset_list",
                        "status": "failed",
                        "error": "tool failed",
                    }
                ],
            }

        result = await run_tenable_mcp_recipe_across_child_containers(
            ["child-1"],
            [{"tool_name": "asset_list"}],
            recipe_runner=fake_recipe_runner,
        )

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["children"][0]["status"], "failed")
        self.assertEqual(result["children"][0]["result"]["failed_step"], 0)

    async def test_concurrency_limit_is_honored(self) -> None:
        """Fan-out should not exceed max_concurrency active child runs."""

        active = 0
        max_seen = 0

        async def fake_recipe_runner(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            nonlocal active, max_seen
            active += 1
            max_seen = max(max_seen, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {
                "child_container_uuid": child_uuid,
                "status": "succeeded",
                "steps": [],
            }

        await run_tenable_mcp_recipe_across_child_containers(
            ["child-1", "child-2", "child-3", "child-4"],
            [{"tool_name": "asset_list"}],
            max_concurrency=2,
            recipe_runner=fake_recipe_runner,
        )

        self.assertLessEqual(max_seen, 2)
        self.assertEqual(max_seen, 2)

    async def test_required_vm_license_skips_ineligible_children(self) -> None:
        """VM license gating should skip children without vm."""

        calls: list[str] = []

        async def fake_recipe_runner(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            calls.append(child_uuid)
            return {
                "child_container_uuid": child_uuid,
                "status": "succeeded",
                "steps": [],
            }

        result = await run_tenable_mcp_recipe_across_child_containers(
            ["child-vm", "child-one"],
            [{"tool_name": "asset_list"}],
            required_license="vm",
            recipe_runner=fake_recipe_runner,
            account_lister=lambda: [
                {"uuid": "child-vm", "licensed_apps": ["vm"]},
                {"uuid": "child-one", "licensed_apps": ["one"]},
            ],
        )

        self.assertEqual(calls, ["child-vm"])
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["children"][1]["status"], "skipped")
        self.assertEqual(
            result["children"][1]["reason"],
            "missing required license: vm",
        )

    async def test_tenable_one_inventory_accepts_one_or_aiv(self) -> None:
        """Tenable One Inventory gating should accept one and aiv."""

        calls: list[str] = []

        async def fake_recipe_runner(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            calls.append(child_uuid)
            return {
                "child_container_uuid": child_uuid,
                "status": "succeeded",
                "steps": [],
            }

        result = await run_tenable_mcp_recipe_across_child_containers(
            ["child-one", "child-aiv", "child-vm"],
            [{"tool_name": "asset_list"}],
            required_license="tenable_one_inventory",
            recipe_runner=fake_recipe_runner,
            account_lister=lambda: [
                {"uuid": "child-one", "licensed_apps": ["one"]},
                {"uuid": "child-aiv", "licensed_apps": ["aiv"]},
                {"uuid": "child-vm", "licensed_apps": ["vm"]},
            ],
        )

        self.assertEqual(calls, ["child-one", "child-aiv"])
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["skipped"], 1)

    async def test_missing_child_account_for_license_gate_is_skipped(self) -> None:
        """Children missing from account lookup should be skipped."""

        async def fail_if_called(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            raise AssertionError("recipe runner should not be called")

        result = await run_tenable_mcp_recipe_across_child_containers(
            ["missing-child"],
            [{"tool_name": "asset_list"}],
            required_license="vm",
            recipe_runner=fail_if_called,
            account_lister=lambda: [],
        )

        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["children"][0]["status"], "skipped")
        self.assertEqual(
            result["children"][0]["reason"],
            "child account not found for required license check",
        )

    async def test_reports_do_not_include_child_api_keys(self) -> None:
        """Returned fan-out reports should not include child API key fields."""

        async def fake_recipe_runner(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            return {
                "child_container_uuid": child_uuid,
                "status": "succeeded",
                "steps": [
                    {
                        "index": 0,
                        "tool_name": "asset_list",
                        "status": "succeeded",
                        "result": {"assets": []},
                    }
                ],
            }

        result = await run_tenable_mcp_recipe_across_child_containers(
            ["child-1"],
            [{"tool_name": "asset_list"}],
            recipe_runner=fake_recipe_runner,
        )

        serialized_report = json.dumps(result)
        self.assertNotIn("access_key", serialized_report)
        self.assertNotIn("secret_key", serialized_report)

    async def test_child_timeout_fails_bad_child_and_allows_others(
        self,
    ) -> None:
        """One timed-out child should not block other child reports."""

        async def fake_recipe_runner(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            if child_uuid == "child-hangs":
                await asyncio.Event().wait()
            return {
                "child_container_uuid": child_uuid,
                "status": "succeeded",
                "steps": [],
            }

        async def fake_wait_for(
            recipe_run: object,
            timeout: int,
        ) -> dict[str, object]:
            child_uuid = recipe_run.cr_frame.f_locals[  # type: ignore[attr-defined]
                "child_uuid"
            ]
            if child_uuid == "child-hangs":
                recipe_run.close()  # type: ignore[attr-defined]
                raise TimeoutError
            return await recipe_run  # type: ignore[misc]

        with patch(
            "simple_mcp.multi_child_tenable_mcp.asyncio.wait_for",
            side_effect=fake_wait_for,
        ):
            result = await run_tenable_mcp_recipe_across_child_containers(
                ["child-ok", "child-hangs"],
                [{"tool_name": "asset_list"}],
                child_timeout_seconds=42,
                recipe_runner=fake_recipe_runner,
            )

        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["children"][0]["status"], "succeeded")
        self.assertEqual(result["children"][1]["status"], "failed")
        self.assertEqual(
            result["children"][1]["error"],
            "child recipe timed out after 42 seconds",
        )

    async def test_child_timeout_none_disables_wait_for(self) -> None:
        """None timeout should run child recipes without asyncio.wait_for."""

        async def fake_recipe_runner(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            return {
                "child_container_uuid": child_uuid,
                "status": "succeeded",
                "steps": [],
            }

        with patch(
            "simple_mcp.multi_child_tenable_mcp.asyncio.wait_for",
            side_effect=AssertionError("wait_for should not be called"),
        ):
            result = await run_tenable_mcp_recipe_across_child_containers(
                ["child-1"],
                [{"tool_name": "asset_list"}],
                child_timeout_seconds=None,
                recipe_runner=fake_recipe_runner,
            )

        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)

    async def test_invalid_inputs_raise_clear_errors(self) -> None:
        """Fan-out input validation should fail before execution."""

        async def fail_if_called(
            child_uuid: str,
            recipe: list[dict[str, object]],
        ) -> dict[str, object]:
            raise AssertionError("recipe runner should not be called")

        invalid_cases = [
            ([], 10, 300, "non-empty list"),
            (["child-1", ""], 10, 300, "item 1"),
            (["child-1"], 0, 300, "max_concurrency"),
            (["child-1"], 10, 0, "child_timeout_seconds"),
            (["child-1"], 10, -1, "child_timeout_seconds"),
            (["child-1"], 10, "bad", "child_timeout_seconds"),
            (["child-1"], 10, True, "child_timeout_seconds"),
        ]

        for (
            child_uuids,
            max_concurrency,
            child_timeout_seconds,
            expected_message,
        ) in invalid_cases:
            with self.subTest(child_uuids=child_uuids):
                with self.assertRaisesRegex(
                    MultiChildRecipeError,
                    expected_message,
                ):
                    await run_tenable_mcp_recipe_across_child_containers(
                        child_uuids,
                        [{"tool_name": "asset_list"}],
                        max_concurrency=max_concurrency,
                        child_timeout_seconds=child_timeout_seconds,
                        recipe_runner=fail_if_called,
                    )  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
