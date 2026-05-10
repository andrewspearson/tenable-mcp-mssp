"""Tests for child account action eligibility checks."""

from __future__ import annotations

import unittest

from tenable_mcp_mssp.child_account_eligibility import (
    ChildAccountEligibilityError,
    CHILD_CONTAINER_OUT_OF_SCOPE_REASON,
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
            scope_checker=lambda child_uuid: True,
        )

        self.assertEqual(account["uuid"], "child-1")

    def test_require_active_child_account_rejects_missing_child(self) -> None:
        """Missing children should not be eligible for action."""

        with self.assertRaisesRegex(
            ChildAccountEligibilityError,
            "not found",
        ):
            require_active_child_account(
                "missing-child",
                account_lister=lambda: [],
                scope_checker=lambda child_uuid: True,
            )

    def test_child_account_ineligible_reason_rejects_expired_child(self) -> None:
        """Expired children should not be eligible for action."""

        reason = child_account_ineligible_reason(
            "child-1",
            {"child-1": {"uuid": "child-1", "license_expiration_date": 1}},
            scope_checker=lambda child_uuid: True,
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
            scope_checker=lambda child_uuid: True,
        )

        self.assertEqual(
            reason,
            "child account license expiration date is missing or invalid",
        )

    def test_child_account_ineligible_reason_rejects_ao_license_type(
        self,
    ) -> None:
        """AO license type children should not be eligible for action."""

        reason = child_account_ineligible_reason(
            "child-1",
            {
                "child-1": {
                    "uuid": "child-1",
                    "license_expiration_date": 4_102_444_800,
                    "licenseType": "ao",
                }
            },
            scope_checker=lambda child_uuid: True,
        )

        self.assertEqual(
            reason,
            "child account license type is excluded from actions",
        )

    def test_child_account_ineligible_reason_rejects_out_of_scope_first(
        self,
    ) -> None:
        """Scope should be checked before account and license details."""

        reason = child_account_ineligible_reason(
            "child-1",
            {},
            scope_checker=lambda child_uuid: False,
        )

        self.assertEqual(reason, CHILD_CONTAINER_OUT_OF_SCOPE_REASON)

    def test_child_account_ineligible_reason_allows_in_scope_active_child(
        self,
    ) -> None:
        """In-scope active children should remain eligible."""

        reason = child_account_ineligible_reason(
            "child-1",
            {
                "child-1": {
                    "uuid": "child-1",
                    "license_expiration_date": 4_102_444_800,
                }
            },
            scope_checker=lambda child_uuid: True,
        )

        self.assertIsNone(reason)

    def test_in_scope_expired_child_remains_rejected(self) -> None:
        """Existing license expiration exclusions should still apply in scope."""

        reason = child_account_ineligible_reason(
            "child-1",
            {"child-1": {"uuid": "child-1", "license_expiration_date": 1}},
            scope_checker=lambda child_uuid: True,
        )

        self.assertEqual(reason, "child account license is expired")

    def test_in_scope_ao_license_type_child_remains_rejected(self) -> None:
        """Existing license type exclusions should still apply in scope."""

        reason = child_account_ineligible_reason(
            "child-1",
            {
                "child-1": {
                    "uuid": "child-1",
                    "license_expiration_date": 4_102_444_800,
                    "licenseType": "ao",
                }
            },
            scope_checker=lambda child_uuid: True,
        )

        self.assertEqual(
            reason,
            "child account license type is excluded from actions",
        )


if __name__ == "__main__":
    unittest.main()
