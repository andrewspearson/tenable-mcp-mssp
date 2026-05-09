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

## Available Tools

- `list_mssp_child_accounts`: List raw MSSP child account objects returned by Tenable, including license data.
- `list_available_tenable_mcp_tools`: Discover the [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tool catalog for one child container.
- `run_tenable_mcp_tool_for_child`: Run one [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tool on one child container for exploration.
- `run_tenable_mcp_recipe_for_child`: Validate a known sequence of [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tool calls on one child container.
- `run_tenable_mcp_recipe_across_child_containers`: Run a known working recipe across multiple child containers with controlled fan-out.

Recommended workflow:

1. List child accounts.
2. Discover available [Tenable Hexa AI MCP Server](https://docs.tenable.com/early-access/vulnerability-management/Content/getting-started/hexa-AI-MCP.htm) tools on one child container.
3. Experiment with single-tool calls on one child container.
4. Validate a known recipe on one child container.
5. Fan out the validated recipe across child containers.
