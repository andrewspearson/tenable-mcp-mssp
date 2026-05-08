"""Helpers for classifying Tenable MSSP child account capabilities."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any


LICENSED_APPS_FIELD = "licensed_apps"
LICENSE_EXPIRATION_DATE_FIELD = "license_expiration_date"
LICENSE_TYPE_FIELD = "licenseType"
EXCLUDED_LICENSE_TYPES = frozenset({"ao"})
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

    return any(
        has_license(account, license_code)
        for license_code in TENABLE_ONE_LICENSES
    )


def supports_vulnerability_management(account: Mapping[str, Any]) -> bool:
    """Return whether a child account supports Vulnerability Management tools."""

    return has_license(account, VULNERABILITY_MANAGEMENT_LICENSE)


def has_excluded_license_type(account: Mapping[str, Any]) -> bool:
    """Return whether a child account has a license type excluded from actions."""

    license_type = account.get(LICENSE_TYPE_FIELD)
    if not isinstance(license_type, str):
        return False

    return license_type.strip().casefold() in EXCLUDED_LICENSE_TYPES


def get_license_expiration_epoch(account: Mapping[str, Any]) -> int | None:
    """Return the license expiration Unix timestamp when it is valid."""

    expiration = account.get(LICENSE_EXPIRATION_DATE_FIELD)
    if isinstance(expiration, bool) or not isinstance(expiration, int):
        return None

    return expiration


def has_valid_license_expiration(
    account: Mapping[str, Any],
    now: int | None = None,
) -> bool:
    """Return whether a child account has a non-expired license timestamp."""

    expiration = get_license_expiration_epoch(account)
    if expiration is None:
        return False

    current_time = _current_epoch_seconds(now)
    return expiration > current_time


def is_license_expired(
    account: Mapping[str, Any],
    now: int | None = None,
) -> bool:
    """Return whether a child account license is expired or invalid."""

    return not has_valid_license_expiration(account, now)


def _current_epoch_seconds(now: int | None = None) -> int:
    """Return the current Unix timestamp in seconds."""

    if now is not None:
        return now

    return int(time.time())
