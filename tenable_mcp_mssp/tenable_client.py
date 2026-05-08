"""Tenable client creation helpers."""

from __future__ import annotations

from tenable.io import TenableIO

from tenable_mcp_mssp.config import Settings, get_settings


def create_tenable_client(settings: Settings | None = None) -> TenableIO:
    """Create a TenableIO client for the MSSP Portal."""

    current_settings = settings or get_settings()

    return TenableIO(
        access_key=current_settings.tenable_access_key,
        secret_key=current_settings.tenable_secret_key,
        vendor=current_settings.tenable_vendor,
        product=current_settings.tenable_product,
        build=current_settings.tenable_build,
    )
