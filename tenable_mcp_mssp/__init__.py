"""Tenable MCP MSSP server package."""

import logging

__all__ = ["__version__"]

__version__ = "0.1.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
