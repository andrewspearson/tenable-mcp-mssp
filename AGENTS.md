### Background
This project provides an MCP server for orchestrating Tenable MSSP child-container workflows.

## Solution
This project provides a Tenable MCP MSSP server for orchestrating Tenable MSSP child-container workflows. It can list raw child account objects from the MSSP Portal, delegate official Tenable MCP tool calls to child containers, enforce scoped child-container actions, validate and fan out known recipes, and run a curated bulk VM CVE export workflow.

Parent MSSP Portal credentials may come from real environment variables or `.env`. Temporary child API keys are generated internally with the [generate child API keys](https://developer.tenable.com/reference/io-mssp-child-containers-generate-keys) endpoint when a tool needs to call Tenable's hosted MCP server for a child container. Generated child keys must stay in memory only and must never be logged, returned, written, or persisted.
Expired child accounts must not be used for any child-container action tool, including official Tenable MCP wrappers and curated tools. Keep `list_mssp_child_accounts` raw so an MSSP can see every child container returned by Tenable, but block or skip action attempts when `license_expiration_date` is missing, malformed, or expired.
Child-container action tools must honor the optional positive allowlist configured by `TENABLE_MCP_MSSP_CHILD_CONTAINER_SCOPE_FILE`. When configured, the allowlist is checked before account/license eligibility gates. It does not override existing exclusions for missing accounts, expired or malformed license expiration data, or `licenseType: "ao"`.

The MCP server is an orchestrator for MSSP child-container work:
1. Use `list_mssp_child_accounts` to get the raw child account objects, including license data.
2. Use `list_available_tenable_mcp_tools(child_container_uuid)` to discover the official Tenable MCP tool catalog for one child container.
3. Use `get_child_container_scope()` when needed to inspect the configured child-container allowlist for action tools.
4. Use `run_tenable_mcp_tool_for_child(child_container_uuid, tool_name, arguments)` to experiment with one official Tenable MCP tool on one child container.
5. After a working sequence is known, use `run_tenable_mcp_recipe_for_child(child_container_uuid, recipe)` to validate that recipe on one child.
6. Use `run_tenable_mcp_recipe_across_child_containers(child_container_uuids, recipe)` only after the recipe is known to work, so fan-out is controlled and predictable. Generic recipe fan-out runs against all hard-eligible requested children and lets the official Tenable MCP tool call succeed or fail per tenant capability.
7. Use `bulk_vm_cve_query(cve_ids)` only when the user explicitly asks for the `bulk_vm_cve_query` tool by name. This curated tool starts a server-managed background run, bypasses the official Tenable MCP server, and uses pyTenable VM exports directly.
8. Use `get_bulk_vm_cve_query_status(run_id)` and `get_bulk_vm_cve_query_result(run_id)` only to observe a `bulk_vm_cve_query` run. The MCP server owns child selection, batching, credentials, retries, and export execution. `run_id` may be omitted to read the latest in-memory bulk query run.

Curated tools may apply internal license gates when the license mapping is deterministic.
Multi-child fan-out uses hard-coded operational safety limits: concurrency is fixed at 10 child containers, and each child recipe run times out after 300 seconds.
Multi-child fan-out emits batch-scoped progress messages. Treat these as observability for the current MCP call, not as durable job state.
Bulk VM CVE queries use the same child-container fan-out controls and hard exclusions, require a `vm` license, write local artifacts under `results/bulk-vm-cve-query/<run-id>/`, and must not return raw findings or secrets through MCP. Run-level bulk query state is kept in memory and is lost if the MCP server restarts, but raw JSONL and aggregate CSV artifacts remain on disk.

## Technology stack
* Python 3.14+
  * [pyTenable](https://github.com/tenable/pyTenable) 1.9.1+
  * [FastMCP](https://pypi.org/project/fastmcp/) 3.2.4+

## Coding guidelines
- In an effort to reduce supply chain attacks, use the standard library as much as possible.
  - pyTenable and FastMCP are permitted. Other Python libraries not in the standard library might be OK to use, but you must ask me if it is OK before implementing it.
  - It is OK to use dependencies imported by approved packages. For example, it is OK to use restfly since it was already imported by pyTenable.
- Code must have clean error handling.
- Code must be secure.
- Parent MSSP Portal API keys must not be leaked and may be supplied only by the real environment or `.env`.
- Generated child API keys must stay memory-only and must never be logged, returned, written, or persisted.
- Preserve secret-safe logging. Do not log API keys, `X-ApiKeys` headers, raw Tenable responses, official MCP results, recipe arguments, or raw finding records.
- Keep public MCP tool schemas intentional. Do not expose operational controls such as concurrency, child timeouts, or child API keys through public tools.
- Code should be idiomatic, follow [PEP 8 guidelines](https://peps.python.org/pep-0008/), well-structured, modular, and easy to read/edit in the future.
- Simple is better than complex.

### Other guidelines
- It is OK to ask questions if Codex is unclear about the instructions.
- It is OK to suggest better ways of achieving the stated goals.
- Only run Python from the virtual environment located at ./.venv
- After changes, run `./.venv/bin/python -m unittest discover -s tests` and `./.venv/bin/python -m compileall tenable_mcp_mssp tests`.
