"""Tests for Tenable MSSP account listing."""

from __future__ import annotations

import unittest

from tenable_mcp_mssp.mssp_accounts import (
    ACCOUNT_LIST_HEADERS,
    ACCOUNT_LIST_PATH,
    AccountListingError,
    list_child_accounts,
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
        """Valid Tenable account payloads should preserve account fields."""

        account_payload = {
            "uuid": "a87cc2b8-29ea-4d71-9903-69e12048c5ac",
            "container_name": "MSSP Example 1",
            "container_uuid": "parent-uuid",
            "created_at": "2026-05-06T00:00:00Z",
        }
        accounts = parse_child_accounts(
            {
                "accounts": [
                    account_payload,
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
                account_payload,
                {
                    "uuid": "33cd81ea-1bea-43d9-a158-8d727089c539",
                    "container_name": "MSSP Example 2",
                },
            ],
        )

    def test_malformed_response_without_accounts_raises_error(self) -> None:
        """A response without the accounts list should fail cleanly."""

        with self.assertRaisesRegex(AccountListingError, "missing accounts list"):
            parse_child_accounts({})

    def test_malformed_account_entry_raises_error(self) -> None:
        """A non-object account entry should fail cleanly."""

        with self.assertRaisesRegex(AccountListingError, "expected an object"):
            parse_child_accounts({"accounts": ["not-an-object"]})


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
                        "container_uuid": "parent-uuid",
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
                {
                    "uuid": "a87cc2b8-29ea-4d71-9903-69e12048c5ac",
                    "container_name": "MSSP Example 1",
                    "container_uuid": "parent-uuid",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
