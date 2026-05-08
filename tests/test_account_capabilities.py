"""Tests for MSSP child account capability helpers."""

from __future__ import annotations

import unittest

from simple_mcp.account_capabilities import (
    has_license,
    supports_tenable_one_inventory,
    supports_vulnerability_management,
)


class AccountCapabilitiesTests(unittest.TestCase):
    """Tests for license-based child account classification."""

    def test_has_license_matches_license_code(self) -> None:
        """The helper should find a requested license in licensed_apps."""

        account = {"licensed_apps": ["vm"]}

        self.assertTrue(has_license(account, "vm"))
        self.assertFalse(has_license(account, "one"))

    def test_has_license_is_case_insensitive(self) -> None:
        """License comparison should tolerate API casing differences."""

        account = {"licensed_apps": ["VM"]}

        self.assertTrue(has_license(account, "vm"))

    def test_supports_vulnerability_management_with_vm_license(self) -> None:
        """The VM license should enable Vulnerability Management support."""

        account = {"licensed_apps": ["vm"]}

        self.assertTrue(supports_vulnerability_management(account))
        self.assertFalse(supports_tenable_one_inventory(account))

    def test_supports_tenable_one_inventory_with_one_license(self) -> None:
        """The one license should enable Tenable One Inventory support."""

        account = {"licensed_apps": ["one"]}

        self.assertTrue(supports_tenable_one_inventory(account))
        self.assertFalse(supports_vulnerability_management(account))

    def test_supports_tenable_one_inventory_with_aiv_license(self) -> None:
        """The aiv license should enable Tenable One Inventory support."""

        account = {"licensed_apps": ["aiv"]}

        self.assertTrue(supports_tenable_one_inventory(account))
        self.assertFalse(supports_vulnerability_management(account))

    def test_missing_license_field_is_safe(self) -> None:
        """Missing license data should be treated as unsupported."""

        account: dict[str, object] = {}

        self.assertFalse(has_license(account, "vm"))
        self.assertFalse(supports_vulnerability_management(account))
        self.assertFalse(supports_tenable_one_inventory(account))

    def test_malformed_license_field_is_safe(self) -> None:
        """Malformed license data should be treated as unsupported."""

        account = {"licensed_apps": "vm"}

        self.assertFalse(has_license(account, "vm"))
        self.assertFalse(supports_vulnerability_management(account))
        self.assertFalse(supports_tenable_one_inventory(account))

    def test_non_string_license_entries_are_ignored(self) -> None:
        """Non-string license entries should not break classification."""

        account = {"licensed_apps": [None, 123, "vm"]}

        self.assertTrue(has_license(account, "vm"))

    def test_blank_license_code_is_safe(self) -> None:
        """Blank requested license codes should not match anything."""

        account = {"licensed_apps": ["vm"]}

        self.assertFalse(has_license(account, ""))
        self.assertFalse(has_license(account, "   "))


if __name__ == "__main__":
    unittest.main()
