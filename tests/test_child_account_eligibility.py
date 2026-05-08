"""Tests for child account action eligibility checks."""

from __future__ import annotations

import unittest

from simple_mcp.child_account_eligibility import (
    ChildAccountEligibilityError,
    build_child_account_lookup,
    child_account_ineligible_reason,
    require_active_child_account,
)


class ChildAccountEligibilityTests(unittest.TestCase):
    """Tests for child account action eligibility."""

    def test_build_child_account_lookup_uses_uuid_keys(self) -> None:
        """The lookup should include accounts with string UUIDs."""

        lookup = build_child_account_lookup(
            lambda: [
                {"uuid": "child-1", "license_expiration_date": 200},
                {"uuid": 123, "license_expiration_date": 200},
            ]
        )

        self.assertEqual(
            lookup,
            {"child-1": {"uuid": "child-1", "license_expiration_date": 200}},
        )

    def test_require_active_child_account_returns_active_account(self) -> None:
        """Active child accounts should be returned for action."""

        account = require_active_child_account(
            "child-1",
            account_lister=lambda: [
                {
                    "uuid": "child-1",
                    "license_expiration_date": 4_102_444_800,
                }
            ],
        )

        self.assertEqual(account["uuid"], "child-1")

    def test_require_active_child_account_rejects_missing_child(self) -> None:
        """Missing children should not be eligible for action."""

        with self.assertRaisesRegex(
            ChildAccountEligibilityError,
            "not found",
        ):
            require_active_child_account("missing-child", account_lister=lambda: [])

    def test_child_account_ineligible_reason_rejects_expired_child(self) -> None:
        """Expired children should not be eligible for action."""

        reason = child_account_ineligible_reason(
            "child-1",
            {"child-1": {"uuid": "child-1", "license_expiration_date": 1}},
        )

        self.assertEqual(reason, "child account license is expired")

    def test_child_account_ineligible_reason_rejects_malformed_expiration(
        self,
    ) -> None:
        """Malformed expiration data should not be eligible for action."""

        reason = child_account_ineligible_reason(
            "child-1",
            {
                "child-1": {
                    "uuid": "child-1",
                    "license_expiration_date": "not-a-timestamp",
                }
            },
        )

        self.assertEqual(
            reason,
            "child account license expiration date is missing or invalid",
        )


if __name__ == "__main__":
    unittest.main()
