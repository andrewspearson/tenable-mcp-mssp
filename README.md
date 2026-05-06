# simple-mcp

A learning project for building a small FastMCP server that lists Tenable MSSP
child accounts.

## Setup

1. Create and activate the virtual environment at `./.venv`.
2. Install the project dependencies from `requirements.txt`.
3. Copy `.env.example` to `.env` and fill in the Tenable API settings.

## Run

```bash
./.venv/bin/python -m simple_mcp.server
```

## Test

```bash
./.venv/bin/python -m unittest discover -s tests
```
