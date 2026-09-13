# VoltBridge MCP

**Public source for evaluation:** free to inspect and test in non-production environments under the [VoltBridge Evaluation License](LICENSE). Production use, resale, hosted offerings and redistribution beyond the license exceptions require separate written permission.

A working Python MCP server for electrical telemetry and maintenance workflows, created for Saad Bin Riaz. Version 0.1.0 is an advanced project foundation for a supervised pilot, not a certified factory-control system or complete SaaS.

Ask an MCP-compatible AI client: **“Read Motor 3, compare its temperature with 45 degC, and prepare a maintenance draft if it is above that limit.”** No paid LLM API is required to run the server or client demo. Natural-language reasoning requires a separate MCP-compatible agent/client and model.

## What works

- Nine typed MCP tools, two resources and one investigation prompt over local stdio.
- Deterministic simulated motor telemetry and a real HTTP connector for gateways implementing the documented JSON contract.
- Voltage, current, power, cumulative energy and temperature with units, UTC timestamps, quality and simulation labels.
- Stale/future timestamp detection; unusable readings cannot pass a threshold check.
- SQLite history collected on reads; company-scoped queries and local maintenance drafts.
- Operator-provisioned viewer, maintenance and admin process roles; audit events and retry-safe draft creation.
- Bounded gateway reads, one network retry, response-size limits, no redirects and HTTPS required when sending a gateway token.
- Automated service, HTTP failure and actual MCP stdio integration tests; GitHub Actions configuration.

## Start on Windows PowerShell

Clone the repository and open its folder:

```powershell
git clone https://github.com/SaadRiaz99/VoltBridge.git
cd VoltBridge
```

Then install and test:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe examples\client_demo.py
```

Python 3.11+ is declared; use Python 3.12 for the locally verified environment. If the `py` launcher is unavailable, use `python -m venv .venv`. Activation is optional because these commands address the environment directly.

The demo launches the server, discovers nine tools, reads simulated Motor 3, checks 48 degC against a 45 degC demo threshold, and stores a local draft. Re-running it reuses the same draft. These are illustrative readings and thresholds, not operating specifications.

Start the server for an MCP host:

```powershell
.\.venv\Scripts\python.exe -m electrical_mcp.server
```

It waits for MCP messages on stdin; it is not an interactive chat prompt or webpage. Diagnostic output goes to stderr. Stop with Ctrl+C.

Linux/macOS: use `python3 -m venv .venv`, then `.venv/bin/python` in place of the Windows Python path.

## Connect an MCP client

For clients accepting an `mcpServers` configuration, adapt this example to your real absolute paths. Client-specific configuration may differ.

```json
{
  "mcpServers": {
    "electrical-electronics": {
      "command": "E:\\Work\\VoltBridge\\.venv\\Scripts\\python.exe",
      "args": ["-m", "electrical_mcp.server"],
      "env": {
        "EEMCP_CONFIG": "E:\\Work\\VoltBridge\\examples\\devices.json",
        "EEMCP_DB": "E:\\Work\\VoltBridge\\electrical-mcp.db",
        "EEMCP_COMPANY": "demo-factory",
        "EEMCP_ROLE": "maintenance"
      }
    }
  }
}
```

The Python package must be installed in the specified environment. Parent directories for the database must exist. The server uses the simulator when `EEMCP_CONFIG` is unset. Environment variables override configuration values. A `.env` file is not automatically loaded.

## Try the HTTP device connection

Terminal 1:

```powershell
.\.venv\Scripts\python.exe examples\http_gateway.py
```

Configure your MCP host with `examples/devices.json`, then call `read_measurements` with `{"device_id":"meter-1"}`. The local gateway returns simulated 3.2 kW with a simulation flag. Stop the gateway to see `get_device_status` return `unavailable`.

For live equipment, replace the configured endpoint with your operator-managed HTTP gateway. It must implement the exact contract in [CONNECTORS.md](docs/CONNECTORS.md). An arbitrary smart meter, PLC or ERP will not automatically work with this connector.

## Tools

| Tool | Purpose | Process role |
|---|---|---|
| `list_devices` | Configured device inventory | All |
| `get_device_capabilities` | Connector and measurement schema | All |
| `read_measurements` | Current sample plus persisted history | All |
| `get_device_status` | Reachability/freshness | All |
| `get_measurement_history` | Up to 500 stored samples in a date range | All |
| `check_threshold` | User-provided maximum with matching unit | All |
| `create_maintenance_request_draft` | Retry-safe local draft | Maintenance/admin |
| `list_maintenance_drafts` | Local drafts for current company | Maintenance/admin |
| `get_audit_events` | Recent operation outcomes | Admin |

Resources: `electrical://devices`, `electrical://integration-guide`.
Prompt: `investigate_device(device_id)`.

Reading tools are read-only with respect to devices, while storing local telemetry/audit records. Drafts never send emails, dispatch technicians, or modify an ERP.

## Boundaries before customer deployment

Use one operator-managed process and separate database/OS account per customer. Company/role configuration is not end-user authentication: anyone who controls the process environment or local database can change/read it. SQL scoping is defense in depth, not a security boundary against the host operator.

This version has no remote MCP endpoint, OAuth, user accounts, billing, dashboard, background polling, ERP dispatch, machine control, MQTT, Modbus or OPC UA implementation. Audit records are local and not tamper-proof. Timestamps/quality are checked, but incoming measurements still depend on a trusted, calibrated gateway. Historical freshness flags describe collection time.

Keep physical protection and emergency interlocks in certified device/PLC systems. For a live pilot, obtain the asset owner's authorization, have a qualified electrical/controls professional provision telemetry access, and test on staging equipment before deployment.

## Project files

| Path | Responsibility |
|---|---|
| `src/electrical_mcp/server.py` | MCP tools, resources, prompt, configuration |
| `src/electrical_mcp/models.py` | Typed device and reading contracts |
| `src/electrical_mcp/connectors.py` | Simulator and HTTP gateway adapter |
| `src/electrical_mcp/service.py` | Permissions and telemetry workflow |
| `src/electrical_mcp/store.py` | SQLite history, drafts and audit |
| `examples/` | Local gateway, sample config, protocol client |
| `tests/` | Business behavior and MCP integration checks |
| `docs/MONETIZATION.md` | Offer, proposed prices and first-customer plan |
| `docs/ROADMAP.md` | Staged expansion and acceptance criteria |
| `docs/PUBLISH_GITHUB.md` | Repository creation and upload instructions |

## SDK choice and sources

This project deliberately uses the supported MCP Python SDK v1 maintenance line (`mcp<2`) and its FastMCP API. SDK v2 has different APIs; do not remove the upper bound without migrating and rerunning the integration tests. See the [official v1 documentation](https://py.sdk.modelcontextprotocol.io/v1/) and [official SDK repository](https://github.com/modelcontextprotocol/python-sdk).

## License and commercial use

VoltBridge uses the custom [VoltBridge Evaluation License 1.0](LICENSE). This is a source-available project, not an open-source-licensed project.

| Use | Permission |
|---|---|
| Inspect, run the simulator, learn and privately modify for non-production evaluation | Allowed under LICENSE |
| Internal business testing to assess suitability | Allowed under LICENSE |
| Share feedback, your benchmark results and screenshots | Allowed subject to LICENSE |
| View or fork on GitHub | GitHub's applicable terms still apply |
| Production operation, resale, hosted service or client deployment | Separate written permission required |
| Redistribute source or modified versions | Restricted, subject to LICENSE exceptions |

Keep license and attribution notices. Third-party dependencies retain their own licenses. A public repository or GitHub fork does not give a blanket commercial-use license.

**Need an integration or commercial license?** Open a [commercial inquiry](https://github.com/SaadRiaz99/VoltBridge/issues/new?title=Commercial%20inquiry) with a non-confidential description of the intended use. Do not post credentials or private customer information. Commercial terms and support scope must be agreed in writing.

These custom terms define permissions; they do not technically prevent copying or guarantee enforcement. They have not been reviewed by a lawyer. Obtain qualified legal review before relying on them for commercial licensing or a dispute. For platform context, see [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
