"""Tests for in-memory child credential storage."""

from __future__ import annotations

import unittest

from tenable_mcp_mssp.child_credentials import (
    ChildCredentialStore,
    ChildCredentialStoreError,
    get_or_generate_child_credentials,
)


def credential_response(
    child_container_uuid: str = "child-uuid",
    access_key: str = "generated-access-key",
    secret_key: str = "generated-secret-key",
    expiration: int = 2_000,
) -> dict[str, object]:
    """Return a fake child key generation response."""

    return {
        "parent_container_uuid": "parent-uuid",
        "child_container_uuid": child_container_uuid,
        "child_container_site": "us-2b",
        "keys_user_uuid": "keys-user-uuid",
        "access_key": access_key,
        "secret_key": secret_key,
        "keys_expiration_epoch_seconds": expiration,
        "remote": False,
        "_validity_info": "2000 60s PT1M 1970-01-01T00:33:20Z",
    }


class ChildCredentialStoreTests(unittest.TestCase):
    """Tests for temporary child credential storage."""

    def test_store_and_retrieve_credentials(self) -> None:
        """Stored credentials should be retrievable by child UUID."""

        store = ChildCredentialStore(clock=lambda: 1_000)

        credential = store.store(credential_response())
        retrieved = store.get("child-uuid")

        self.assertEqual(retrieved, credential)
        self.assertEqual(retrieved.access_key, "generated-access-key")
        self.assertEqual(retrieved.secret_key, "generated-secret-key")

    def test_public_metadata_excludes_secrets(self) -> None:
        """Public metadata should not include access or secret keys."""

        store = ChildCredentialStore(clock=lambda: 1_000)

        metadata = store.store(credential_response()).public_metadata()

        self.assertNotIn("access_key", metadata)
        self.assertNotIn("secret_key", metadata)
        self.assertEqual(metadata["child_container_uuid"], "child-uuid")
        self.assertEqual(metadata["stored"], True)

    def test_missing_access_key_rejects_storage(self) -> None:
        """Responses without access keys should not be stored."""

        store = ChildCredentialStore(clock=lambda: 1_000)
        response = credential_response()
        response.pop("access_key")

        with self.assertRaisesRegex(ChildCredentialStoreError, "access_key"):
            store.store(response)

    def test_missing_secret_key_rejects_storage(self) -> None:
        """Responses without secret keys should not be stored."""

        store = ChildCredentialStore(clock=lambda: 1_000)
        response = credential_response()
        response.pop("secret_key")

        with self.assertRaisesRegex(ChildCredentialStoreError, "secret_key"):
            store.store(response)

    def test_expired_credentials_are_rejected(self) -> None:
        """Expired generated credentials should not be stored."""

        store = ChildCredentialStore(clock=lambda: 1_000)

        with self.assertRaisesRegex(ChildCredentialStoreError, "expired"):
            store.store(credential_response(expiration=999))

        with self.assertRaisesRegex(ChildCredentialStoreError, "No stored"):
            store.get("child-uuid")

    def test_get_removes_expired_credentials(self) -> None:
        """Credentials should be removed when they expire before retrieval."""

        now = 1_000
        store = ChildCredentialStore(clock=lambda: now)
        store.store(credential_response(expiration=1_001))

        now = 1_002

        with self.assertRaisesRegex(ChildCredentialStoreError, "expired"):
            store.get("child-uuid")

        with self.assertRaisesRegex(ChildCredentialStoreError, "No stored"):
            store.get("child-uuid")

    def test_clear_expired_removes_only_expired_entries(self) -> None:
        """clear_expired should keep valid credentials."""

        store = ChildCredentialStore(clock=lambda: 1_000)
        store.store(
            credential_response(
                child_container_uuid="expired-child",
                expiration=1_001,
            )
        )
        store.store(
            credential_response(
                child_container_uuid="valid-child",
                expiration=2_000,
            )
        )

        store._clock = lambda: 1_002
        store.clear_expired()

        with self.assertRaisesRegex(ChildCredentialStoreError, "No stored"):
            store.get("expired-child")
        self.assertEqual(store.get("valid-child").child_container_uuid, "valid-child")

    def test_get_or_generate_reuses_valid_credentials(self) -> None:
        """Valid stored credentials should be reused without generation."""

        store = ChildCredentialStore(clock=lambda: 1_000)
        stored_credential = store.store(credential_response())

        def fail_generator(child_container_uuid: str) -> dict[str, object]:
            raise AssertionError("key generator should not be called")

        credential = get_or_generate_child_credentials(
            "child-uuid",
            key_generator=fail_generator,
            store=store,
        )

        self.assertEqual(credential, stored_credential)

    def test_get_or_generate_generates_missing_credentials(self) -> None:
        """Missing credentials should trigger internal key generation."""

        store = ChildCredentialStore(clock=lambda: 1_000)

        credential = get_or_generate_child_credentials(
            "child-uuid",
            key_generator=lambda child_uuid: credential_response(
                child_container_uuid=child_uuid,
            ),
            store=store,
        )

        self.assertEqual(credential.child_container_uuid, "child-uuid")
        self.assertEqual(store.get("child-uuid"), credential)

    def test_get_or_generate_regenerates_expired_credentials(self) -> None:
        """Expired credentials should trigger internal key regeneration."""

        now = 1_000
        store = ChildCredentialStore(clock=lambda: now)
        store.store(credential_response(access_key="old-key", expiration=1_001))
        now = 1_002

        credential = get_or_generate_child_credentials(
            "child-uuid",
            key_generator=lambda child_uuid: credential_response(
                child_container_uuid=child_uuid,
                access_key="new-key",
                expiration=2_000,
            ),
            store=store,
        )

        self.assertEqual(credential.access_key, "new-key")


if __name__ == "__main__":
    unittest.main()
