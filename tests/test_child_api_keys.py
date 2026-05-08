"""Tests for Tenable MSSP child API key generation."""

from __future__ import annotations

import unittest

from tenable_mcp_mssp.child_api_keys import (
    CHILD_KEYS_HEADERS,
    CHILD_KEYS_PATH,
    ChildApiKeyGenerationError,
    build_child_key_request_body,
    generate_child_api_keys,
    parse_child_api_key_response,
)


class FakeResponse:
    """Minimal fake response for pyTenable-style JSON calls."""

    def __init__(self, payload: object) -> None:
        self.payload = payload

    def json(self) -> object:
        """Return the fake response payload."""

        return self.payload


class FakeTenableClient:
    """Minimal fake client for child API key generation tests."""

    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.path: str | None = None
        self.json: dict[str, object] | None = None
        self.headers: dict[str, str] | None = None

    def post(
        self,
        path: str,
        json: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        """Capture the request and return a fake response."""

        self.path = path
        self.json = json
        self.headers = headers
        return FakeResponse(self.payload)


class BuildChildKeyRequestBodyTests(unittest.TestCase):
    """Tests for child API key request validation."""

    def test_required_child_container_uuid_body(self) -> None:
        """The default request should only include the child UUID."""

        self.assertEqual(
            build_child_key_request_body(" child-uuid "),
            {"child_container_uuid": "child-uuid"},
        )

    def test_custom_validity_duration_body(self) -> None:
        """A valid custom duration should be included in the request body."""

        self.assertEqual(
            build_child_key_request_body("child-uuid", 60),
            {
                "child_container_uuid": "child-uuid",
                "keys_validity_duration_seconds": 60,
            },
        )

    def test_blank_child_container_uuid_raises_error(self) -> None:
        """Blank child UUIDs should fail before making an API call."""

        with self.assertRaisesRegex(
            ChildApiKeyGenerationError,
            "child_container_uuid",
        ):
            build_child_key_request_body(" ")

    def test_duration_over_maximum_raises_error(self) -> None:
        """Durations over Tenable's maximum should fail before the API call."""

        with self.assertRaisesRegex(
            ChildApiKeyGenerationError,
            "between 1 and 3600",
        ):
            build_child_key_request_body("child-uuid", 3601)


class GenerateChildApiKeysTests(unittest.TestCase):
    """Tests for child API key generation."""

    def test_successful_post_with_required_uuid(self) -> None:
        """The generator should call the documented endpoint."""

        response_payload = {
            "parent_container_uuid": "parent-uuid",
            "child_container_uuid": "child-uuid",
            "child_container_site": "us-2b",
            "keys_user_uuid": "keys-user-uuid",
            "access_key": "generated-access-key",
            "secret_key": "generated-secret-key",
            "keys_expiration_epoch_seconds": 1680627675,
            "remote": False,
            "_validity_info": "1680627675 60s PT1M 2023-04-04T17:01:15Z",
        }
        client = FakeTenableClient(response_payload)

        generated_keys = generate_child_api_keys("child-uuid", client=client)

        self.assertEqual(client.path, CHILD_KEYS_PATH)
        self.assertEqual(
            client.json,
            {"child_container_uuid": "child-uuid"},
        )
        self.assertEqual(client.headers, CHILD_KEYS_HEADERS)
        self.assertEqual(generated_keys, response_payload)

    def test_successful_post_with_custom_duration(self) -> None:
        """A custom duration should be sent when provided."""

        client = FakeTenableClient(
            {
                "child_container_uuid": "child-uuid",
                "access_key": "generated-access-key",
                "secret_key": "generated-secret-key",
            }
        )

        generate_child_api_keys("child-uuid", 60, client=client)

        self.assertEqual(
            client.json,
            {
                "child_container_uuid": "child-uuid",
                "keys_validity_duration_seconds": 60,
            },
        )

    def test_malformed_non_object_response_raises_error(self) -> None:
        """A non-object API response should fail cleanly."""

        client = FakeTenableClient(["not-an-object"])

        with self.assertRaisesRegex(
            ChildApiKeyGenerationError,
            "expected an object",
        ):
            generate_child_api_keys("child-uuid", client=client)

    def test_parse_preserves_full_response_including_keys(self) -> None:
        """The parser should preserve all generated key response fields."""

        response_payload = {
            "child_container_uuid": "child-uuid",
            "access_key": "generated-access-key",
            "secret_key": "generated-secret-key",
            "extra_field": {"nested": True},
        }

        self.assertEqual(
            parse_child_api_key_response(response_payload),
            response_payload,
        )


if __name__ == "__main__":
    unittest.main()
