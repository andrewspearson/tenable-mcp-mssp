# Tenable MSSP Portal MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/badge/python-3.14-blue)

A FastMCP server for orchestrating Tenable MSSP child container workflows.

## Features

- List raw Tenable MSSP child account objects, including license data.
- Generate temporary child API keys internally for child-container MCP calls.
- Keep generated child API keys in process memory only; public tools do not return them.
- Discover [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tools for a child container.
- Run one [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tool against one child container for exploration.
- Validate a known recipe of [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tool calls on one child container.
- Run a known recipe across multiple child containers with eligibility checks, fixed concurrency, per-child timeouts, and batch progress messages.
- Start an explicitly requested curated bulk VM CVE query as a server-managed background run that writes local JSONL and CSV artifacts.

## Prerequisites

- Python 3.14 or newer.
- Tenable MSSP Portal API keys.
- `uv` or `pip` for local installation.
- An MCP client capable of launching STDIO MCP servers (Codex, Claude, Gemini CLI, etc.).

## Setup
1. **Download with `git`:**

   ```bash
   git clone https://github.com/andrewspearson/tenable-mcp-mssp.git
   ```
   ```bash
   cd tenable-mcp-mssp
   ```

2. **Install dependencies with `uv` or `pip`:**

   Using `uv`:

   ```bash
   uv venv
   ```
   ```bash
   uv pip install .
   ```

   Using `pip`:

   ```bash
   python3 -m venv .venv
   ```
   ```bash
   source .venv/bin/activate
   ```
   ```bash
   pip install .
   ```

3. **Copy and edit environment variables:**

   ```bash
   cp .env.example .env
   ```
   ```bash
   chmod 600 .env
   ```
   ```bash
   vim .env
   ```
   .env example:
   ```text
   TENABLE_MSSP_PORTAL_ACCESS_KEY=replace-with-your-access-key
   TENABLE_MSSP_PORTAL_SECRET_KEY=replace-with-your-secret-key
   # Optional: path to a plain-text child container UUID allowlist.
   # TENABLE_MCP_MSSP_CHILD_CONTAINER_SCOPE_FILE=scopes/allowed-child-containers.txt
   # Optional: DEBUG, INFO, WARNING, ERROR, or CRITICAL
   # TENABLE_MCP_MSSP_LOG_LEVEL=WARNING
   ```

4. **Attach Codex / Claude / Gemini CLI / etc. to tenable-mcp-mssp as a STDIO server:**

   [Codex](https://developers.openai.com/codex/mcp#add-an-mcp-server):
   ```bash
   codex mcp add tenable-mcp-mssp -- /path/to/tenable-mcp-mssp/.venv/bin/python -m tenable_mcp_mssp.server
   ```
   [Claude](https://code.claude.com/docs/en/mcp#option-3-add-a-local-stdio-server):
   ```bash
   claude mcp add tenable-mcp-mssp -- /path/to/tenable-mcp-mssp/.venv/bin/python -m tenable_mcp_mssp.server
   ```
   [Gemini CLI](https://geminicli.com/docs/tools/mcp-server/#adding-a-server-gemini-mcp-add):
   ```bash
   gemini mcp add tenable-mcp-mssp /path/to/tenable-mcp-mssp/.venv/bin/python -m tenable_mcp_mssp.server
   ```

## Child Container Scope

Set `TENABLE_MCP_MSSP_CHILD_CONTAINER_SCOPE_FILE` to restrict child-container action tools to an explicit positive allowlist. If this value is unset or blank, all otherwise eligible child containers are allowed.

The scope file is plain text with one child container UUID per line. Blank lines and full-line comments starting with `#` are ignored.

```text
# production batch 1
75e2d005-946b-46fe-8e73-7887d310de33
b210fe55-741b-49b4-ac3d-cafec153006f
```

Relative scope paths are resolved from the MCP server's configured working directory. The allowlist is checked before other eligibility gates, but it does not override existing exclusions: expired children, malformed expiration data, missing child accounts, and `licenseType: "ao"` children are still blocked from action.

## Logging
Set `TENABLE_MCP_MSSP_LOG_LEVEL` to `DEBUG`, `INFO`, `WARNING`(default), `ERROR`, or `CRITICAL`. All logs are sent to `stderr`.
```bash
codex mcp add --env TENABLE_MCP_MSSP_LOG_LEVEL=DEBUG tenable-mcp-mssp -- /bin/sh -c 'exec /path/to/tenable-mcp-mssp/.venv/bin/python -m tenable_mcp_mssp.server 2>> /path/to/logs/tenable-mcp-mssp.log'
```

## Available Tools

- `list_mssp_child_accounts`: List raw MSSP child account objects returned by Tenable, including license data.
- `list_available_tenable_mcp_tools`: Discover the [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tool catalog for one child container.
- `get_child_container_scope`: Show the configured child container allowlist scope for action tools.
- `run_tenable_mcp_tool_for_child`: Run one [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tool on one child container for exploration.
- `run_tenable_mcp_recipe_for_child`: Validate a known sequence of [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tool calls on one child container.
- `run_tenable_mcp_recipe_across_child_containers`: Run a known working recipe across multiple child containers with controlled fan-out.
- `bulk_vm_cve_query`: Start a curated direct pyTenable VM export for CVEs across eligible child containers. This tool should be used only when explicitly requested by name.
- `get_bulk_vm_cve_query_status`: Check status for a server-managed `bulk_vm_cve_query` run.
- `get_bulk_vm_cve_query_result`: Read final summary and artifact paths for a server-managed `bulk_vm_cve_query` run.

Recommended workflow:

1. List child accounts.
2. Discover available [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tools on one child container.
3. Experiment with single-tool calls on one child container.
4. Validate a known recipe on one child container.
5. Fan out the validated recipe across child containers.

The `bulk_vm_cve_query` tool is separate from the standard Hexa AI MCP workflow. It accepts only a CVE list, derives eligible VM child containers internally, honors the configured child container scope and exclusions, writes raw JSONL exports plus an aggregate CSV under `results/bulk-vm-cve-query/<run-id>/`, and returns a `run_id` quickly. Use `get_bulk_vm_cve_query_status` and `get_bulk_vm_cve_query_result` to observe the server-managed run; these tools do not control child selection, batching, credentials, retries, or export execution. Run-level status is kept in memory and is lost if the MCP server restarts, but generated artifact files remain on disk.
