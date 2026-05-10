"""Tests for configured child container allowlist scope."""

from __future__ import annotations

import io
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tenable_mcp_mssp.child_container_scope import (
    CHILD_CONTAINER_SCOPE_FILE_ENV,
    get_child_container_scope,
    is_child_container_in_scope,
    load_child_container_scope,
)
from tenable_mcp_mssp.config import ConfigurationError


UUID_ONE = "75e2d005-946b-46fe-8e73-7887d310de33"
UUID_TWO = "b210fe55-741b-49b4-ac3d-cafec153006f"


class ChildContainerScopeTests(unittest.TestCase):
    """Tests for child container scope loading and reporting."""

    def setUp(self) -> None:
        """Start each test with a fresh cached scope."""

        load_child_container_scope.cache_clear()

    def tearDown(self) -> None:
        """Clear cached scope between tests."""

        load_child_container_scope.cache_clear()

    def test_unset_env_disables_scope(self) -> None:
        """Missing scope configuration should allow all children."""

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("tenable_mcp_mssp.child_container_scope.load_dotenv"),
        ):
            scope = load_child_container_scope()

        self.assertFalse(scope.scope_enabled)
        self.assertIsNone(scope.source)
        self.assertEqual(scope.count, 0)
        self.assertTrue(is_child_container_in_scope("any-child"))

    def test_valid_scope_file_loads_uuid_entries(self) -> None:
        """Scope files should load unique UUIDs and ignore comments."""

        with tempfile.TemporaryDirectory() as tmpdir:
            scope_file = Path(tmpdir) / "allowed.txt"
            scope_file.write_text(
                "\n".join(
                    [
                        "# production children",
                        UUID_TWO,
                        "",
                        UUID_ONE,
                        UUID_ONE,
                    ]
                ),
                encoding="utf-8",
            )

            with (
                patch.dict(
                    os.environ,
                    {CHILD_CONTAINER_SCOPE_FILE_ENV: str(scope_file)},
                    clear=True,
                ),
                patch("tenable_mcp_mssp.child_container_scope.load_dotenv"),
            ):
                report = get_child_container_scope()

        self.assertTrue(report["scope_enabled"])
        self.assertEqual(report["count"], 2)
        self.assertEqual(
            report["allowed_child_container_uuids"],
            sorted([UUID_ONE, UUID_TWO]),
        )

    def test_relative_scope_path_resolves_from_working_directory(self) -> None:
        """Relative scope files should resolve from the process cwd."""

        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            scope_file = Path(tmpdir) / "scopes" / "allowed.txt"
            scope_file.parent.mkdir()
            scope_file.write_text(UUID_ONE, encoding="utf-8")

            try:
                os.chdir(tmpdir)
                with (
                    patch.dict(
                        os.environ,
                        {CHILD_CONTAINER_SCOPE_FILE_ENV: "scopes/allowed.txt"},
                        clear=True,
                    ),
                    patch("tenable_mcp_mssp.child_container_scope.load_dotenv"),
                ):
                    scope = load_child_container_scope()
            finally:
                os.chdir(original_cwd)

        self.assertEqual(scope.source, str(scope_file.resolve()))
        self.assertTrue(scope.allows(UUID_ONE))

    def test_invalid_uuid_entry_raises_clear_error(self) -> None:
        """Invalid scope entries should fail closed with line context."""

        with tempfile.TemporaryDirectory() as tmpdir:
            scope_file = Path(tmpdir) / "allowed.txt"
            scope_file.write_text(f"{UUID_ONE}\nnot-a-uuid\n", encoding="utf-8")

            with (
                patch.dict(
                    os.environ,
                    {CHILD_CONTAINER_SCOPE_FILE_ENV: str(scope_file)},
                    clear=True,
                ),
                patch("tenable_mcp_mssp.child_container_scope.load_dotenv"),
            ):
                with self.assertRaisesRegex(ConfigurationError, "line 2"):
                    load_child_container_scope()

    def test_missing_scope_file_fails_closed(self) -> None:
        """A configured but missing scope file should fail closed."""

        with tempfile.TemporaryDirectory() as tmpdir:
            missing_file = Path(tmpdir) / "missing.txt"

            with (
                patch.dict(
                    os.environ,
                    {CHILD_CONTAINER_SCOPE_FILE_ENV: str(missing_file)},
                    clear=True,
                ),
                patch("tenable_mcp_mssp.child_container_scope.load_dotenv"),
            ):
                with self.assertRaisesRegex(ConfigurationError, "Unable to read"):
                    load_child_container_scope()

    def test_empty_scope_file_allows_zero_children(self) -> None:
        """An empty configured scope should be valid and allow no children."""

        with tempfile.TemporaryDirectory() as tmpdir:
            scope_file = Path(tmpdir) / "empty.txt"
            scope_file.write_text("# no children currently allowed\n", encoding="utf-8")

            with (
                patch.dict(
                    os.environ,
                    {CHILD_CONTAINER_SCOPE_FILE_ENV: str(scope_file)},
                    clear=True,
                ),
                patch("tenable_mcp_mssp.child_container_scope.load_dotenv"),
            ):
                scope = load_child_container_scope()

        self.assertTrue(scope.scope_enabled)
        self.assertEqual(scope.count, 0)
        self.assertFalse(scope.allows(UUID_ONE))

    def test_scope_logging_is_secret_safe(self) -> None:
        """Representative scope logs should avoid secret-like data."""

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("tenable_mcp_mssp.child_container_scope")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        with tempfile.TemporaryDirectory() as tmpdir:
            scope_file = Path(tmpdir) / "allowed.txt"
            scope_file.write_text(UUID_ONE, encoding="utf-8")

            try:
                with (
                    patch.dict(
                        os.environ,
                        {CHILD_CONTAINER_SCOPE_FILE_ENV: str(scope_file)},
                        clear=True,
                    ),
                    patch("tenable_mcp_mssp.child_container_scope.load_dotenv"),
                ):
                    load_child_container_scope()
            finally:
                logger.removeHandler(handler)

        logs = log_stream.getvalue()
        self.assertIn("Child container scope is enabled", logs)
        self.assertIn("1 UUIDs", logs)
        self.assertNotIn("access_key", logs)
        self.assertNotIn("secret_key", logs)
        self.assertNotIn("X-ApiKeys", logs)


if __name__ == "__main__":
    unittest.main()
