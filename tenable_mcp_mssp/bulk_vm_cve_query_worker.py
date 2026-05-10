"""Subprocess worker for one child VM CVE export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tenable.io import TenableIO


def main() -> int:
    """Run a single child VM CVE export."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-file", required=True)
    parser.add_argument("--status-file", required=True)
    args = parser.parse_args()

    status_file = Path(args.status_file)
    raw_file = Path(args.raw_file)

    try:
        payload = json.loads(sys.stdin.read())
        finding_count = export_child_vulnerabilities(payload, raw_file)
        write_status(
            status_file,
            {
                "status": "succeeded",
                "raw_file_path": str(raw_file),
                "finding_count": finding_count,
            },
        )
        return 0
    except Exception as exc:
        payload = payload if isinstance(locals().get("payload"), dict) else {}
        write_status(
            status_file,
            {
                "status": "failed",
                "error": sanitize_error(str(exc), payload),
            },
        )
        return 1


def export_child_vulnerabilities(payload: dict[str, Any], raw_file: Path) -> int:
    """Export child vulnerability findings to JSONL."""

    client = TenableIO(
        access_key=payload["access_key"],
        secret_key=payload["secret_key"],
        vendor=payload["vendor"],
        product=payload["product"],
        build=payload["build"],
    )
    cve_ids = payload["cve_ids"]
    finding_count = 0
    raw_file.parent.mkdir(parents=True, exist_ok=True)

    with raw_file.open("w", encoding="utf-8") as file:
        for finding in client.exports.vulns(cve_id=cve_ids):
            file.write(json.dumps(finding, separators=(",", ":")))
            file.write("\n")
            finding_count += 1

    return finding_count


def write_status(status_file: Path, payload: dict[str, Any]) -> None:
    """Write the worker status payload."""

    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(payload), encoding="utf-8")


def sanitize_error(message: str, payload: dict[str, Any]) -> str:
    """Remove credential values from a worker error message."""

    sanitized_message = message
    for key in ("access_key", "secret_key"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            sanitized_message = sanitized_message.replace(value, "<redacted>")

    return sanitized_message


if __name__ == "__main__":
    raise SystemExit(main())
