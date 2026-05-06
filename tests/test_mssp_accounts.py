"""Tests for Tenable MSSP account listing."""

from __future__ import annotations

import unittest

from simple_mcp.mssp_accounts import (
    ACCOUNT_LIST_HEADERS,
    ACCOUNT_LIST_PATH,
    AccountListingError,
    ChildAccount,
    list_child_accounts,
    list_child_accounts_as_dicts,
    parse_child_accounts,
)


class FakeResponse:
    """Minimal fake response for pyTenable-style JSON calls."""

    def __init__(self, payload: object) -> None:
        self.payload = payload

    def json(self) -> object:
        """Return the fake response payload."""

        return self.payload


class FakeTenableClient:
    """Minimal fake client for account listing tests."""

    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.path: str | None = None
        self.headers: dict[str, str] | None = None

    def get(self, path: str, headers: dict[str, str] | None = None) -> FakeResponse:
        """Capture the request and return a fake response."""

        self.path = path
        self.headers = headers
        return FakeResponse(self.payload)


class ParseChildAccountsTests(unittest.TestCase):
    """Tests for account response parsing."""

    def test_successful_tenant_parsing(self) -> None:
        """Valid Tenable account payloads should return name and UUID only."""

        accounts = parse_child_accounts(
            {
                "accounts": [
                    {
                        "uuid": "a87cc2b8-29ea-4d71-9903-69e12048c5ac",
                        "container_name": "MSSP Example 1",
                        "container_uuid": "ignored-parent-uuid",
                    },
                    {
                        "uuid": "33cd81ea-1bea-43d9-a158-8d727089c539",
                        "container_name": "MSSP Example 2",
                    },
                ],
            }
        )

        self.assertEqual(
            accounts,
            [
                ChildAccount(
                    name="MSSP Example 1",
                    uuid="a87cc2b8-29ea-4d71-9903-69e12048c5ac",
                ),
                ChildAccount(
                    name="MSSP Example 2",
                    uuid="33cd81ea-1bea-43d9-a158-8d727089c539",
                ),
            ],
        )

    def test_malformed_response_without_accounts_raises_error(self) -> None:
        """A response without the accounts list should fail cleanly."""

        with self.assertRaisesRegex(AccountListingError, "missing accounts list"):
            parse_child_accounts({})

    def test_malformed_account_without_uuid_raises_error(self) -> None:
        """An account without a UUID should fail cleanly."""

        with self.assertRaisesRegex(AccountListingError, "missing uuid"):
            parse_child_accounts(
                {"accounts": [{"container_name": "MSSP Example"}]}
            )

    def test_malformed_account_without_name_raises_error(self) -> None:
        """An account without a name should fail cleanly."""

        with self.assertRaisesRegex(AccountListingError, "missing container_name"):
            parse_child_accounts({"accounts": [{"uuid": "tenant-uuid"}]})


class ListChildAccountsTests(unittest.TestCase):
    """Tests for the Tenable client boundary."""

    def test_list_child_accounts_uses_expected_endpoint(self) -> None:
        """The listing function should call the documented MSSP endpoint."""

        client = FakeTenableClient(
            {
                "accounts": [
                    {
                        "uuid": "a87cc2b8-29ea-4d71-9903-69e12048c5ac",
                        "container_name": "MSSP Example 1",
                    }
                ]
            }
        )

        accounts = list_child_accounts(client)

        self.assertEqual(client.path, ACCOUNT_LIST_PATH)
        self.assertEqual(client.headers, ACCOUNT_LIST_HEADERS)
        self.assertEqual(
            accounts,
            [
                ChildAccount(
                    name="MSSP Example 1",
                    uuid="a87cc2b8-29ea-4d71-9903-69e12048c5ac",
                )
            ],
        )

    def test_list_child_accounts_as_dicts_returns_json_friendly_values(self) -> None:
        """The MCP-facing helper should return dictionaries."""

        client = FakeTenableClient(
            {
                "accounts": [
                    {
                        "uuid": "33cd81ea-1bea-43d9-a158-8d727089c539",
                        "container_name": "MSSP Example 2",
                    }
                ]
            }
        )

        accounts = list_child_accounts_as_dicts(client)

        self.assertEqual(
            accounts,
            [
                {
                    "name": "MSSP Example 2",
                    "uuid": "33cd81ea-1bea-43d9-a158-8d727089c539",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
