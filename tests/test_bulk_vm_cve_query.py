"""Tests for curated bulk VM CVE query helpers."""

from __future__ import annotations

import asyncio
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tenable_mcp_mssp.bulk_vm_cve_query import (
    BulkVmCveQueryError,
    aggregate_bulk_query_results,
    bulk_vm_cve_query,
    normalize_finding_for_csv,
    run_child_export_process,
    validate_cve_ids,
)
from tenable_mcp_mssp.bulk_vm_cve_query_worker import export_child_vulnerabilities
from tenable_mcp_mssp.bulk_vm_cve_query_worker import sanitize_error as sanitize_worker_error
from tenable_mcp_mssp.child_credentials import ChildCredential


ACTIVE_LICENSE_EXPIRATION = 4_102_444_800


class BulkVmCveQueryValidationTests(unittest.TestCase):
    """Tests for bulk CVE input validation."""

    def test_validate_cve_ids_normalizes_and_deduplicates(self) -> None:
        """CVE input should normalize uppercase and preserve first occurrence."""

        self.assertEqual(
            validate_cve_ids([" cve-2021-44228 ", "CVE-2021-44228", "CVE-2017-5715"]),
            ["CVE-2021-44228", "CVE-2017-5715"],
        )

    def test_validate_cve_ids_rejects_invalid_input(self) -> None:
        """Malformed CVE input should raise clear validation errors."""

        invalid_cases = [
            [],
            ["not-a-cve"],
            ["CVE-2024-123"],
            [123],
        ]

        for cve_ids in invalid_cases:
            with self.subTest(cve_ids=cve_ids):
                with self.assertRaises(BulkVmCveQueryError):
                    validate_cve_ids(cve_ids)  # type: ignore[arg-type]


class BulkVmCveQueryTests(unittest.IsolatedAsyncioTestCase):
    """Tests for bulk VM CVE query orchestration."""

    async def test_bulk_query_exports_only_eligible_vm_children(self) -> None:
        """Only scoped, active VM children should run exports."""

        calls: list[str] = []

        async def fake_process_runner(
            child_uuid: str,
            account: object,
            credential: ChildCredential,
            cve_ids: list[str],
            raw_directory: Path,
            status_directory: Path,
        ) -> dict[str, object]:
            calls.append(child_uuid)
            raw_file = raw_directory / f"{child_uuid}.jsonl"
            raw_file.write_text(
                json.dumps(
                    {
                        "asset": {"hostname": child_uuid, "ipv4": "192.0.2.1"},
                        "plugin": {
                            "id": 100,
                            "name": "Plugin",
                            "cve": cve_ids,
                        },
                        "severity": "high",
                        "finding_id": f"finding-{child_uuid}",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return {
                "status": "succeeded",
                "raw_file_path": str(raw_file),
                "finding_count": 1,
                "child_container_name": str(account["container_name"]),  # type: ignore[index]
            }

        accounts = [
            active_account("vm-child", "VM Child", ["vm"]),
            active_account("one-child", "One Child", ["one"]),
            active_account("ao-child", "AO Child", ["vm"], license_type="ao"),
            {"uuid": "expired-child", "container_name": "Expired", "license_expiration_date": 1, "licensed_apps": ["vm"]},
            active_account("out-of-scope", "Out", ["vm"]),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "tenable_mcp_mssp.child_account_eligibility."
                "is_child_container_in_scope",
                side_effect=lambda child_uuid: child_uuid != "out-of-scope",
            ):
                result = await bulk_vm_cve_query(
                    ["CVE-2021-44228"],
                    account_lister=lambda: accounts,
                    credential_getter=fake_credential,
                    process_runner=fake_process_runner,
                    results_root=Path(tmpdir),
                )

        self.assertEqual(calls, ["vm-child"])
        self.assertEqual(result["queued"], 5)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["skipped"], 4)
        self.assertEqual(result["total_findings"], 1)
        self.assertNotIn("access-key", json.dumps(result))
        self.assertNotIn("secret-key", json.dumps(result))

    async def test_process_cancellation_terminates_child_process(self) -> None:
        """Cancelled process exports should terminate the worker process."""

        process = FakeProcess()

        async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeProcess:
            return process

        with patch(
            "tenable_mcp_mssp.bulk_vm_cve_query.asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            task = asyncio.create_task(
                run_child_export_process(
                    "child-1",
                    active_account("child-1", "Child", ["vm"]),
                    fake_credential("child-1"),
                    ["CVE-2021-44228"],
                    Path("/tmp/raw"),
                    Path("/tmp/status"),
                )
            )
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertTrue(process.terminated)


class BulkVmCveQueryArtifactTests(unittest.TestCase):
    """Tests for raw export writing and aggregate CSV output."""

    def test_worker_writes_jsonl_one_finding_per_line(self) -> None:
        """The subprocess worker export helper should write valid JSONL."""

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_file = Path(tmpdir) / "child.jsonl"
            with patch(
                "tenable_mcp_mssp.bulk_vm_cve_query_worker.TenableIO",
                return_value=FakeTenableIO(
                    [
                        {"finding_id": "finding-1"},
                        {"finding_id": "finding-2"},
                    ]
                ),
            ):
                count = export_child_vulnerabilities(
                    {
                        "access_key": "access-key",
                        "secret_key": "secret-key",
                        "vendor": "vendor",
                        "product": "product",
                        "build": "build",
                        "cve_ids": ["CVE-2021-44228"],
                    },
                    raw_file,
                )

            lines = raw_file.read_text(encoding="utf-8").splitlines()

        self.assertEqual(count, 2)
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["finding_id"], "finding-1")
        self.assertEqual(json.loads(lines[1])["finding_id"], "finding-2")

    def test_worker_error_sanitizer_redacts_credentials(self) -> None:
        """Worker errors should not preserve credential values."""

        message = "request failed for access-key and secret-key"
        sanitized = sanitize_worker_error(
            message,
            {"access_key": "access-key", "secret_key": "secret-key"},
        )

        self.assertEqual(sanitized, "request failed for <redacted> and <redacted>")

    def test_aggregate_csv_writes_expected_columns_and_sorted_rows(self) -> None:
        """Aggregate CSV should flatten and sort successful child exports."""

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_a = Path(tmpdir) / "a.jsonl"
            raw_b = Path(tmpdir) / "b.jsonl"
            aggregate_csv = Path(tmpdir) / "aggregate.csv"
            raw_a.write_text(
                json.dumps(sample_finding("zeta", "finding-a")) + "\n",
                encoding="utf-8",
            )
            raw_b.write_text(
                json.dumps(sample_finding("alpha", "finding-b")) + "\n",
                encoding="utf-8",
            )
            total = aggregate_bulk_query_results(
                [
                    {
                        "child_container_uuid": "child-z",
                        "status": "succeeded",
                        "result": {
                            "raw_file_path": str(raw_a),
                            "child_container_name": "Zulu",
                        },
                    },
                    {
                        "child_container_uuid": "child-a",
                        "status": "succeeded",
                        "result": {
                            "raw_file_path": str(raw_b),
                            "child_container_name": "Alpha",
                        },
                    },
                    {"child_container_uuid": "failed", "status": "failed"},
                ],
                aggregate_csv,
            )
            with aggregate_csv.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual(total, 2)
        self.assertEqual(rows[0]["child_container_name"], "Alpha")
        self.assertEqual(rows[0]["asset_name"], "alpha")
        self.assertEqual(rows[0]["plugin_id"], "12345")
        self.assertEqual(rows[0]["finding_id"], "finding-b")
        self.assertEqual(rows[0]["cves"], "CVE-2021-44228;CVE-2021-45046")
        self.assertEqual(rows[0]["cvss_v4_base_score"], "")
        self.assertEqual(rows[1]["child_container_name"], "Zulu")

    def test_missing_nested_fields_become_blank_csv_values(self) -> None:
        """Missing nested export data should become blank CSV fields."""

        row = normalize_finding_for_csv("child-1", "Child", {})

        self.assertEqual(row["asset_name"], "")
        self.assertEqual(row["plugin_name"], "")
        self.assertEqual(row["vpr_score"], "")


def active_account(
    child_uuid: str,
    name: str,
    licensed_apps: list[str],
    license_type: str = "ep",
) -> dict[str, object]:
    """Return an active fake child account."""

    return {
        "uuid": child_uuid,
        "container_name": name,
        "license_expiration_date": ACTIVE_LICENSE_EXPIRATION,
        "licensed_apps": licensed_apps,
        "licenseType": license_type,
    }


def fake_credential(child_uuid: str) -> ChildCredential:
    """Return fake child credentials."""

    return ChildCredential(
        child_container_uuid=child_uuid,
        access_key="access-key",
        secret_key="secret-key",
    )


def sample_finding(asset_name: str, finding_id: str) -> dict[str, object]:
    """Return a sample VM export finding."""

    return {
        "asset": {
            "hostname": asset_name,
            "ipv4": "192.0.2.10",
        },
        "plugin": {
            "id": 12345,
            "name": "Sample Plugin",
            "cve": ["CVE-2021-44228", "CVE-2021-45046"],
            "cvss_base_score": 5.0,
            "cvss3_base_score": 7.5,
            "vpr": {"score": 8.9},
        },
        "port": {"port": 443},
        "severity": "high",
        "finding_id": finding_id,
    }


class FakeExports:
    """Fake pyTenable exports API."""

    def __init__(self, findings: list[dict[str, object]]) -> None:
        self._findings = findings

    def vulns(self, cve_id: list[str]) -> list[dict[str, object]]:
        """Return fake vulnerability findings."""

        return self._findings


class FakeTenableIO:
    """Fake TenableIO client."""

    def __init__(self, findings: list[dict[str, object]]) -> None:
        self.exports = FakeExports(findings)


class FakeProcess:
    """Fake asyncio subprocess that blocks until cancelled."""

    returncode: int | None = None

    def __init__(self) -> None:
        self.terminated = False

    async def communicate(self, input: bytes) -> tuple[bytes, bytes]:
        """Block forever to simulate a stuck process."""

        await asyncio.Event().wait()
        return b"", b""

    def terminate(self) -> None:
        """Record process termination."""

        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        """Record process kill."""

        self.returncode = -9

    async def wait(self) -> int:
        """Return the fake process exit code."""

        return self.returncode or 0


if __name__ == "__main__":
    unittest.main()
