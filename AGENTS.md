### Background
This project provides an MCP server for orchestrating Tenable MSSP child-container workflows.

## Solution
In this project we are going to create a Tenable MCP MSSP server with tools for interacting with a Tenable MSSP Portal. The first tool will [list all child accounts](https://developer.tenable.com/reference/io-mssp-accounts-list) connected to a Tenable MSSP Portal. It will take the following actions:
1. Authenticate to the MSSP Portal with API keys utilizing the [pyTenable](https://github.com/tenable/pyTenable) Python library.
2. [List all connected child tenants](https://developer.tenable.com/reference/io-mssp-accounts-list).
3. Report the full child/tenant account objects returned by the API.

Temporary child API keys are generated internally with the [generate child API keys](https://developer.tenable.com/reference/io-mssp-child-containers-generate-keys) endpoint when a tool needs to call Tenable's hosted MCP server for a child container. Generated child keys must stay in memory only and must not be returned by public MCP tools.
Expired child accounts must not be used for official Tenable MCP actions. Keep `list_mssp_child_accounts` raw so an MSSP can see every child container returned by Tenable, but block or skip action attempts when `license_expiration_date` is missing, malformed, or expired.
Child-container action tools must honor the optional positive allowlist configured by `TENABLE_MCP_MSSP_CHILD_CONTAINER_SCOPE_FILE`. When configured, the allowlist is checked before account/license eligibility gates. It does not override existing exclusions for missing accounts, expired or malformed license expiration data, or `licenseType: "ao"`.

The MCP server is an orchestrator for MSSP child-container work:
1. Use `list_mssp_child_accounts` to get the raw child account objects, including license data.
2. Use `list_available_tenable_mcp_tools(child_container_uuid)` to discover the official Tenable MCP tool catalog for one child container.
3. Use `get_child_container_scope()` when needed to inspect the configured child-container allowlist for action tools.
4. Use `run_tenable_mcp_tool_for_child(child_container_uuid, tool_name, arguments)` to experiment with one official Tenable MCP tool on one child container.
5. After a working sequence is known, use `run_tenable_mcp_recipe_for_child(child_container_uuid, recipe)` to validate that recipe on one child.
6. Use `run_tenable_mcp_recipe_across_child_containers(child_container_uuids, recipe)` only after the recipe is known to work, so fan-out is controlled and predictable. Generic recipe fan-out runs against all hard-eligible requested children and lets the official Tenable MCP tool call succeed or fail per tenant capability.
7. Use `bulk_vm_cve_query(cve_ids)` only when the user explicitly asks for the `bulk_vm_cve_query` tool by name. This curated tool bypasses the official Tenable MCP server and uses pyTenable VM exports directly.

Curated tools may apply internal license gates when the license mapping is deterministic.
Multi-child fan-out uses hard-coded operational safety limits: concurrency is fixed at 10 child containers, and each child recipe run times out after 300 seconds.
Multi-child fan-out emits batch-scoped progress messages. Treat these as observability for the current MCP call, not as durable job state.
Bulk VM CVE queries use the same child-container fan-out controls and hard exclusions, require a `vm` license, write local artifacts under `results/bulk-vm-cve-query/<timestamp>/`, and must not return raw findings or secrets through MCP.

Here is an example of how to use [pyTenable](https://pytenable.readthedocs.io/en/stable/api/base/platform.html) to:
1. Authenticate to the Tenable MSSP Portal via API keys.
2. List all connected child tenants.
```
from tenable.io import TenableIO

# Create a client to interact with the MSSP Portal
parent_client = TenableIO(
    access_key='',
    secret_key='',
    vendor='company name',
    product='integration name',
    build='1.0.0'
)

headers = {'Content-Type': 'application/json'}

# List MSSP child accounts
print('fetching list of child accounts')
accounts = parent_client.get('mssp/accounts', headers=headers).json()
```

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
- API keys must not be leaked or stored persistently anywhere other than the .env file.
- Code should be idiomatic, follow [PEP 8 guidelines](https://peps.python.org/pep-0008/), well-structured, modular, and easy to read/edit in the future.
- Simple is better than complex.

### Other guidelines
- It is OK to ask questions if Codex is unclear about the instructions.
- It is OK to suggest better ways of achieving the stated goals.
- Only run Python from the virtual environment located at ./.venv

## Implementation sequence
1. **Project skeleton**
   Set up the MCP server entrypoint, dependency files, `.env.example`, and basic config loading.
2. **Tenable client wrapper**
   Add a small module that reads API keys from environment variables and creates a `TenableIO` client.
3. **MSSP account listing function**
   Implement the logic that calls `mssp/accounts`, parses the response, and returns the full child/tenant account objects returned by the API.
4. **FastMCP tool**
   Expose that function as one MCP tool.
5. **Error handling and testing**
   Add focused tests for missing keys, malformed API responses, and successful tenant parsing.
