"""Helpers for classifying Tenable MSSP child account capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


LICENSED_APPS_FIELD = "licensed_apps"
TENABLE_ONE_LICENSES = frozenset({"one", "aiv"})
VULNERABILITY_MANAGEMENT_LICENSE = "vm"


def has_license(account: Mapping[str, Any], license_code: str) -> bool:
    """Return whether a child account has the requested license code."""

    if not isinstance(license_code, str) or not license_code.strip():
        return False

    licensed_apps = account.get(LICENSED_APPS_FIELD)
    if not isinstance(licensed_apps, list):
        return False

    requested_license = license_code.strip().casefold()
    return any(
        isinstance(app, str) and app.strip().casefold() == requested_license
        for app in licensed_apps
    )


def supports_tenable_one_inventory(account: Mapping[str, Any]) -> bool:
    """Return whether a child account supports Tenable One Inventory tools."""

    return any(has_license(account, license_code) for license_code in TENABLE_ONE_LICENSES)


def supports_vulnerability_management(account: Mapping[str, Any]) -> bool:
    """Return whether a child account supports Vulnerability Management tools."""

    return has_license(account, VULNERABILITY_MANAGEMENT_LICENSE)
