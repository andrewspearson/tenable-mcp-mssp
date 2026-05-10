"""Curated bulk CVE query using Tenable VM vulnerability exports."""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import re
import sys
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tenable_mcp_mssp import __version__
from tenable_mcp_mssp.account_capabilities import VULNERABILITY_MANAGEMENT_LICENSE
from tenable_mcp_mssp.child_credentials import (
    ChildCredential,
    get_or_generate_child_credentials,
)
from tenable_mcp_mssp.child_fanout import (
    DEFAULT_CHILD_TIMEOUT_SECONDS,
    DEFAULT_MAX_CONCURRENCY,
    ProgressReporter,
    run_child_fanout,
)
from tenable_mcp_mssp.config import INTEGRATION_PRODUCT, INTEGRATION_VENDOR
from tenable_mcp_mssp.mssp_accounts import list_child_accounts


BULK_QUERY_RESULTS_DIR = Path("results") / "bulk-vm-cve-query"
CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)
CSV_COLUMNS = [
    "child_container_uuid",
    "child_container_name",
    "asset_name",
    "ipv4",
    "ipv6",
    "port",
    "cves",
    "plugin_id",
    "plugin_name",
    "finding_id",
    "severity",
    "cvss_v2_base_score",
    "cvss_v3_base_score",
    "cvss_v4_base_score",
    "vpr_score",
]
logger = logging.getLogger(__name__)


class BulkVmCveQueryError(ValueError):
    """Raised when bulk VM CVE query input is invalid."""


@dataclass
class BulkVmCveQueryRun:
    """In-memory state for one bulk VM CVE query run."""

    run_id: str
    cve_ids: list[str]
    run_directory: Path
    raw_directory: Path
    aggregate_csv: Path
    started_at: str
    status: str = "running"
    completed_at: str | None = None
    queued: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    total_findings: int = 0
    children: list[dict[str, object]] = field(default_factory=list)
    latest_progress_message: str = "Bulk VM CVE query run started."
    error: str | None = None
    task: asyncio.Task[None] | None = field(default=None, repr=False)


_RUNS: dict[str, BulkVmCveQueryRun] = {}
_LATEST_RUN_ID: str | None = None


async def bulk_vm_cve_query(
    cve_ids: list[str],
    account_lister: Callable[[], list[dict[str, Any]]] = list_child_accounts,
    credential_getter: Callable[
        [str],
        ChildCredential,
    ] = get_or_generate_child_credentials,
    process_runner: Callable[
        [str, Mapping[str, Any], ChildCredential, list[str], Path, Path],
        Awaitable[dict[str, object]],
    ] | None = None,
    progress_reporter: ProgressReporter | None = None,
    results_root: Path = BULK_QUERY_RESULTS_DIR,
) -> dict[str, object]:
    """Start a background bulk VM CVE query across eligible child containers."""

    validated_cves = validate_cve_ids(cve_ids)
    run_id = build_run_id()
    run_directory = results_root / run_id
    raw_directory = run_directory / "raw"
    status_directory = run_directory / "status"
    aggregate_csv = run_directory / f"aggregate-report-{run_id}.csv"
    raw_directory.mkdir(parents=True, exist_ok=True)
    status_directory.mkdir(parents=True, exist_ok=True)
    run = BulkVmCveQueryRun(
        run_id=run_id,
        cve_ids=validated_cves,
        run_directory=run_directory,
        raw_directory=raw_directory,
        aggregate_csv=aggregate_csv,
        started_at=current_timestamp(),
    )
    register_bulk_vm_cve_query_run(run)
    run.task = asyncio.create_task(
        _execute_bulk_vm_cve_query_run(
            run,
            status_directory,
            account_lister,
            credential_getter,
            process_runner,
            progress_reporter,
        )
    )

    logger.info("Started background bulk VM CVE query run %s.", run_id)
    return build_run_report(run, include_children=False)


def get_bulk_vm_cve_query_status(run_id: str | None = None) -> dict[str, object]:
    """Return status for a background bulk VM CVE query run."""

    run = get_bulk_vm_cve_query_run(run_id)
    return build_run_report(run, include_children=False)


def get_bulk_vm_cve_query_result(run_id: str | None = None) -> dict[str, object]:
    """Return result details for a background bulk VM CVE query run."""

    run = get_bulk_vm_cve_query_run(run_id)
    return build_run_report(run, include_children=True)


async def wait_for_bulk_vm_cve_query_run(run_id: str) -> None:
    """Wait for a run to finish. Intended for tests and internal checks."""

    run = get_bulk_vm_cve_query_run(run_id)
    if run.task is not None:
        await run.task


def register_bulk_vm_cve_query_run(run: BulkVmCveQueryRun) -> None:
    """Register a bulk VM CVE query run in memory."""

    global _LATEST_RUN_ID
    _RUNS[run.run_id] = run
    _LATEST_RUN_ID = run.run_id


def get_bulk_vm_cve_query_run(run_id: str | None = None) -> BulkVmCveQueryRun:
    """Return an in-memory bulk VM CVE query run."""

    selected_run_id = run_id or _LATEST_RUN_ID
    if not selected_run_id:
        raise BulkVmCveQueryError("bulk VM CVE query run not found.")

    run = _RUNS.get(selected_run_id)
    if run is None:
        raise BulkVmCveQueryError("bulk VM CVE query run not found.")

    return run


def clear_bulk_vm_cve_query_runs() -> None:
    """Clear in-memory bulk VM CVE query runs. Intended for tests."""

    global _LATEST_RUN_ID
    _RUNS.clear()
    _LATEST_RUN_ID = None


async def _execute_bulk_vm_cve_query_run(
    run: BulkVmCveQueryRun,
    status_directory: Path,
    account_lister: Callable[[], list[dict[str, Any]]],
    credential_getter: Callable[[str], ChildCredential],
    process_runner: Callable[
        [str, Mapping[str, Any], ChildCredential, list[str], Path, Path],
        Awaitable[dict[str, object]],
    ] | None,
    progress_reporter: ProgressReporter | None,
) -> None:
    """Execute a registered bulk VM CVE query run in the background."""

    try:
        result = await _run_bulk_vm_cve_query_exports(
            run,
            status_directory,
            account_lister,
            credential_getter,
            process_runner,
            progress_reporter,
        )
    except Exception as exc:
        run.status = "failed"
        run.completed_at = current_timestamp()
        run.error = str(exc)
        run.latest_progress_message = "Bulk VM CVE query run failed."
        logger.warning("Failed background bulk VM CVE query run %s.", run.run_id)
        return

    run.status = str(result["status"])
    run.completed_at = current_timestamp()
    run.queued = int(result["queued"])
    run.succeeded = int(result["succeeded"])
    run.failed = int(result["failed"])
    run.skipped = int(result["skipped"])
    run.total_findings = int(result["total_findings"])
    children = result.get("children")
    run.children = children if isinstance(children, list) else []
    run.latest_progress_message = (
        "Bulk VM CVE query run complete: "
        f"{run.succeeded} succeeded, {run.failed} failed, "
        f"{run.skipped} skipped."
    )


async def _run_bulk_vm_cve_query_exports(
    run: BulkVmCveQueryRun,
    status_directory: Path,
    account_lister: Callable[[], list[dict[str, Any]]],
    credential_getter: Callable[[str], ChildCredential],
    process_runner: Callable[
        [str, Mapping[str, Any], ChildCredential, list[str], Path, Path],
        Awaitable[dict[str, object]],
    ] | None,
    progress_reporter: ProgressReporter | None,
) -> dict[str, object]:
    """Run the full bulk VM CVE query export workflow."""

    accounts = account_lister()
    child_uuids = [
        account["uuid"]
        for account in accounts
        if isinstance(account.get("uuid"), str)
    ]
    run.queued = len(child_uuids)
    runner = process_runner or run_child_export_process

    logger.info(
        "Started bulk VM CVE query run %s for %d CVEs across %d child accounts.",
        run.run_id,
        len(run.cve_ids),
        len(child_uuids),
    )

    async def report_progress(done: int, total: int, message: str) -> None:
        run.latest_progress_message = message
        if progress_reporter is not None:
            await progress_reporter(done, total, message)

    async def child_worker(
        child_container_uuid: str,
        account: Mapping[str, Any],
    ) -> dict[str, object]:
        credential = credential_getter(child_container_uuid)
        return await runner(
            child_container_uuid,
            account,
            credential,
            run.cve_ids,
            run.raw_directory,
            status_directory,
        )

    fanout_report = await run_child_fanout(
        child_uuids,
        child_worker,
        required_license=VULNERABILITY_MANAGEMENT_LICENSE,
        max_concurrency=DEFAULT_MAX_CONCURRENCY,
        child_timeout_seconds=DEFAULT_CHILD_TIMEOUT_SECONDS,
        account_lister=lambda: accounts,
        progress_reporter=report_progress,
        operation_name="bulk VM CVE export",
        timeout_error_label="child export",
        allow_empty=True,
    )
    total_findings = aggregate_bulk_query_results(
        fanout_report["children"],
        run.aggregate_csv,
    )
    status = "succeeded" if fanout_report["failed"] == 0 else "partial_failure"

    logger.info(
        "Completed bulk VM CVE query: %d succeeded, %d failed, %d skipped.",
        fanout_report["succeeded"],
        fanout_report["failed"],
        fanout_report["skipped"],
    )
    return {
        "status": status,
        "cve_ids": run.cve_ids,
        "run_directory": str(run.run_directory),
        "raw_directory": str(run.raw_directory),
        "aggregate_csv": str(run.aggregate_csv),
        "queued": fanout_report["queued"],
        "succeeded": fanout_report["succeeded"],
        "failed": fanout_report["failed"],
        "skipped": fanout_report["skipped"],
        "total_findings": total_findings,
        "children": fanout_report["children"],
    }


def validate_cve_ids(cve_ids: Any) -> list[str]:
    """Validate, normalize, and de-duplicate CVE IDs."""

    if not isinstance(cve_ids, list) or not cve_ids:
        raise BulkVmCveQueryError("cve_ids must be a non-empty list.")

    validated_cves: list[str] = []
    seen_cves: set[str] = set()
    for index, cve_id in enumerate(cve_ids):
        if not isinstance(cve_id, str) or not cve_id.strip():
            raise BulkVmCveQueryError(
                f"cve_ids item {index} must be a non-empty string."
            )

        normalized_cve = cve_id.strip().upper()
        if not CVE_PATTERN.fullmatch(normalized_cve):
            raise BulkVmCveQueryError(
                f"cve_ids item {index} must match CVE-YYYY-NNNN format."
            )

        if normalized_cve not in seen_cves:
            seen_cves.add(normalized_cve)
            validated_cves.append(normalized_cve)

    return validated_cves


async def run_child_export_process(
    child_container_uuid: str,
    account: Mapping[str, Any],
    credential: ChildCredential,
    cve_ids: list[str],
    raw_directory: Path,
    status_directory: Path,
) -> dict[str, object]:
    """Run one child export in a subprocess and return its status."""

    raw_file = raw_directory / f"{child_container_uuid}.jsonl"
    status_file = status_directory / f"{child_container_uuid}.json"
    payload = {
        "access_key": credential.access_key,
        "secret_key": credential.secret_key,
        "vendor": INTEGRATION_VENDOR,
        "product": INTEGRATION_PRODUCT,
        "build": __version__,
        "cve_ids": cve_ids,
    }
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "tenable_mcp_mssp.bulk_vm_cve_query_worker",
        "--raw-file",
        str(raw_file),
        "--status-file",
        str(status_file),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    logger.info("Started bulk VM CVE export for child %s.", child_container_uuid)
    try:
        stderr = await _communicate_with_export_process(process, payload)
    except asyncio.CancelledError:
        await _terminate_export_process(process)
        logger.warning(
            "Terminated bulk VM CVE export for child %s.",
            child_container_uuid,
        )
        raise

    status_payload = read_worker_status(status_file)
    if process.returncode != 0 or status_payload.get("status") != "succeeded":
        error = status_payload.get("error") or "child export process failed"
        if stderr and not status_payload.get("error"):
            error = "child export process failed"
        error = sanitize_error(str(error), credential)
        return {
            "status": "failed",
            "error": error,
            "raw_file_path": str(raw_file),
        }

    finding_count = status_payload.get("finding_count", 0)
    logger.info(
        "Completed bulk VM CVE export for child %s with %s findings.",
        child_container_uuid,
        finding_count,
    )
    return {
        "status": "succeeded",
        "raw_file_path": str(raw_file),
        "finding_count": finding_count,
        "child_container_name": get_child_container_name(account),
    }


async def _communicate_with_export_process(
    process: asyncio.subprocess.Process,
    payload: dict[str, object],
) -> bytes:
    """Send payload to the worker process and wait for completion."""

    _, stderr = await process.communicate(
        json.dumps(payload).encode("utf-8")
    )
    return stderr or b""


async def _terminate_export_process(process: asyncio.subprocess.Process) -> None:
    """Terminate a child export process after cancellation."""

    if process.returncode is not None:
        return

    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except TimeoutError:
        process.kill()
        await process.wait()


def read_worker_status(status_file: Path) -> dict[str, object]:
    """Read a worker status payload from disk."""

    if not status_file.exists():
        return {"status": "failed", "error": "child export status file missing"}

    try:
        status_payload = json.loads(status_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "failed", "error": "child export status file invalid"}

    if not isinstance(status_payload, dict):
        return {"status": "failed", "error": "child export status file invalid"}

    return status_payload


def aggregate_bulk_query_results(
    children: object,
    aggregate_csv: Path,
) -> int:
    """Aggregate successful raw JSONL files into a sorted CSV report."""

    rows: list[dict[str, object]] = []
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict) or child.get("status") != "succeeded":
                continue

            result = child.get("result")
            if not isinstance(result, dict):
                continue

            raw_file_path = result.get("raw_file_path")
            if not isinstance(raw_file_path, str):
                continue

            child_uuid = str(child.get("child_container_uuid", ""))
            child_name = str(result.get("child_container_name", child_uuid))
            rows.extend(
                normalize_finding_for_csv(child_uuid, child_name, finding)
                for finding in iter_jsonl_findings(Path(raw_file_path))
            )

    rows.sort(
        key=lambda row: (
            str(row["child_container_name"]).casefold(),
            str(row["child_container_uuid"]).casefold(),
            str(row["asset_name"]).casefold(),
        )
    )
    aggregate_csv.parent.mkdir(parents=True, exist_ok=True)
    with aggregate_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(
        "Wrote aggregate bulk VM CVE report to %s with %d findings.",
        aggregate_csv,
        len(rows),
    )
    return len(rows)


def iter_jsonl_findings(raw_file: Path) -> list[dict[str, Any]]:
    """Return JSON objects from a raw JSONL export file."""

    findings: list[dict[str, Any]] = []
    try:
        with raw_file.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    findings.append(payload)
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to read raw bulk VM CVE export file %s.", raw_file)

    return findings


def normalize_finding_for_csv(
    child_container_uuid: str,
    child_container_name: str,
    finding: Mapping[str, Any],
) -> dict[str, object]:
    """Flatten one vulnerability export finding into a CSV row."""

    asset = get_mapping(finding.get("asset"))
    plugin = get_mapping(finding.get("plugin"))
    port = get_mapping(finding.get("port"))
    vpr = get_mapping(plugin.get("vpr"))
    return {
        "child_container_uuid": child_container_uuid,
        "child_container_name": child_container_name,
        "asset_name": first_text(
            asset.get("hostname"),
            asset.get("fqdn"),
            asset.get("netbios_name"),
            asset.get("uuid"),
        ),
        "ipv4": join_if_list(asset.get("ipv4")),
        "ipv6": join_if_list(asset.get("ipv6")),
        "port": text_or_blank(port.get("port")),
        "cves": join_if_list(plugin.get("cve")),
        "plugin_id": text_or_blank(plugin.get("id")),
        "plugin_name": text_or_blank(plugin.get("name")),
        "finding_id": text_or_blank(finding.get("finding_id")),
        "severity": text_or_blank(finding.get("severity")),
        "cvss_v2_base_score": text_or_blank(plugin.get("cvss_base_score")),
        "cvss_v3_base_score": text_or_blank(plugin.get("cvss3_base_score")),
        "cvss_v4_base_score": first_text(
            plugin.get("cvss4_base_score"),
            plugin.get("cvss_v4_base_score"),
        ),
        "vpr_score": text_or_blank(vpr.get("score")),
    }


def get_mapping(value: Any) -> Mapping[str, Any]:
    """Return value when it is a mapping, otherwise an empty mapping."""

    if isinstance(value, Mapping):
        return value

    return {}


def get_child_container_name(account: Mapping[str, Any]) -> str:
    """Return a display name for a child container account."""

    return first_text(
        account.get("container_name"),
        account.get("name"),
        account.get("uuid"),
    )


def first_text(*values: Any) -> str:
    """Return the first non-empty text value."""

    for value in values:
        text = text_or_blank(value)
        if text:
            return text

    return ""


def join_if_list(value: Any) -> str:
    """Return a semicolon-delimited string for lists, or text for scalars."""

    if isinstance(value, list):
        return ";".join(text_or_blank(item) for item in value if text_or_blank(item))

    return text_or_blank(value)


def text_or_blank(value: Any) -> str:
    """Return a simple text representation for CSV output."""

    if value is None:
        return ""

    return str(value)


def build_timestamp() -> str:
    """Return a filesystem-friendly UTC timestamp."""

    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_run_id() -> str:
    """Return a unique bulk query run ID."""

    return f"{build_timestamp()}-{uuid.uuid4().hex[:8]}"


def current_timestamp() -> str:
    """Return an ISO-formatted UTC timestamp."""

    return datetime.now(UTC).isoformat()


def build_run_report(
    run: BulkVmCveQueryRun,
    include_children: bool,
) -> dict[str, object]:
    """Return a JSON-friendly report for an in-memory run."""

    report: dict[str, object] = {
        "run_id": run.run_id,
        "status": run.status,
        "cve_ids": run.cve_ids,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "run_directory": str(run.run_directory),
        "raw_directory": str(run.raw_directory),
        "aggregate_csv": str(run.aggregate_csv),
        "queued": run.queued,
        "succeeded": run.succeeded,
        "failed": run.failed,
        "skipped": run.skipped,
        "total_findings": run.total_findings,
        "latest_progress_message": run.latest_progress_message,
    }
    if run.error:
        report["error"] = run.error
    if include_children:
        report["children"] = run.children

    return report


def sanitize_error(message: str, credential: ChildCredential) -> str:
    """Remove child credential values from an error message."""

    sanitized_message = message
    for value in (credential.access_key, credential.secret_key):
        if value:
            sanitized_message = sanitized_message.replace(value, "<redacted>")

    return sanitized_message
