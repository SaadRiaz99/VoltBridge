# VoltBridge MCP

**Public source for evaluation:** free to inspect and test in non-production environments under the [VoltBridge Evaluation License](LICENSE). Production use, resale, hosted offerings and redistribution beyond the license exceptions require separate written permission.

A working Python MCP server for electrical telemetry and maintenance workflows, created for Saad Bin Riaz. Version 0.3.0 includes advanced analytics, real-time monitoring, alerting, device grouping, and scheduling capabilities.

Ask an MCP-compatible AI client: **"Read Motor 3, compare its temperature with 45 degC, and prepare a maintenance draft if it is above that limit."** No paid LLM API is required to run the server or client demo. Natural-language reasoning requires a separate MCP-compatible agent/client and model.

## What works

- **25+ typed MCP tools** with advanced analytics, alerting, device grouping, scheduling, and data export.
- Deterministic simulated motor telemetry and real HTTP/MQTT connectors for gateways.
- Voltage, current, power, cumulative energy and temperature with units, UTC timestamps, quality and simulation labels.
- **Advanced analytics**: trend analysis, anomaly detection, forecasting, and pattern recognition.
- **Configurable alerting**: threshold-based alerts with notifications and escalation.
- **Device grouping**: organize devices into hierarchical groups for fleet management.
- **Scheduled tasks**: automated monitoring, reporting, and data collection.
- **Data export**: JSON, CSV, Parquet, and Excel formats.
- **Real-time monitoring**: WebSocket support for live telemetry streaming.
- **MQTT integration**: connect to IoT devices via MQTT protocol.
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
.\\.venv\\Scripts\\python.exe -m pip install -e ".[dev]"
.\\.venv\\Scripts\\python.exe -m pytest -q
.\\.venv\\Scripts\\python.exe examples\\client_demo.py
```

Python 3.11+ is declared; use Python 3.12 for the locally verified environment. If the `py` launcher is unavailable, use `python -m venv .venv`. Activation is optional because these commands address the environment directly.

### Install with optional dependencies

```powershell
# With MQTT support
.\\.venv\\Scripts\\python.exe -m pip install -e ".[mqtt]"

# With Parquet export
.\\.venv\\Scripts\\python.exe -m pip install -e ".[parquet]"

# With all optional dependencies
.\\.venv\\Scripts\\python.exe -m pip install -e ".[dev,mqtt,parquet]"
```

The demo launches the server, discovers 25+ tools, reads simulated Motor 3, runs analytics, creates alert rules, and demonstrates all advanced features. These are illustrative readings and thresholds, not operating specifications.

Start the server for an MCP host:

```powershell
.\\.venv\\Scripts\\python.exe -m electrical_mcp.server
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
.\\.venv\\Scripts\\python.exe examples\\http_gateway.py
```

Configure your MCP host with `examples/devices.json`, then call `read_measurements` with `{"device_id":"meter-1"}`. The local gateway returns simulated 3.2 kW with a simulation flag. Stop the gateway to see `get_device_status` return `unavailable`.

For live equipment, replace the configured endpoint with your operator-managed HTTP gateway. It must implement the exact contract in [CONNECTORS.md](docs/CONNECTORS.md). An arbitrary smart meter, PLC or ERP will not automatically work with this connector.

## Tools

### Core Telemetry Tools

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
| `get_fleet_health` | Bounded fleet reachability and telemetry-quality overview | All |
| `get_measurement_statistics` | Per-metric minimum, maximum and sample mean | All |
| `compare_device_measurements` | Quality-checked comparison of two device readings | All |

### Advanced Analytics Tools

| Tool | Purpose | Process role |
|---|---|---|
| `analyze_device_telemetry` | Advanced analytics with trends, anomalies, and forecasts | All |
| `detect_anomalies` | Statistical anomaly detection in telemetry data | All |
| `forecast_telemetry` | Simple linear forecast based on historical trends | All |

### Alert Management Tools

| Tool | Purpose | Process role |
|---|---|---|
| `create_alert_rule` | Create configurable alert thresholds | Admin |
| `list_alert_rules` | List alert rules with optional filtering | All |
| `get_active_alerts` | Get currently active alerts | All |
| `acknowledge_alert` | Acknowledge an active alert | Maintenance/admin |
| `resolve_alert` | Resolve an active or acknowledged alert | Maintenance/admin |
| `get_alert_statistics` | Get alert system statistics | Admin |

### Device Group Tools

| Tool | Purpose | Process role |
|---|---|---|
| `create_device_group` | Create a new device group | Admin |
| `add_device_to_group` | Add a device to a group | Admin |
| `list_device_groups` | List device groups | All |
| `get_device_groups` | Get groups containing a device | All |
| `get_group_hierarchy` | Get complete device group hierarchy | All |

### Scheduled Task Tools

| Tool | Purpose | Process role |
|---|---|---|
| `create_scheduled_task` | Create automated monitoring tasks | Admin |
| `list_scheduled_tasks` | List all scheduled tasks | All |
| `run_task_now` | Immediately execute a task | Admin |
| `get_task_history` | Get task execution history | All |

### Data Export Tools

| Tool | Purpose | Process role |
|---|---|---|
| `export_device_data` | Export telemetry data in JSON/CSV format | All |
| `generate_device_report` | Generate comprehensive device report | All |

Resources: `electrical://devices`, `electrical://integration-guide`.
Prompt: `investigate_device(device_id)`.

Reading tools are read-only with respect to devices, while storing local telemetry/audit records. Drafts never send emails, dispatch technicians, or modify an ERP.

## New in v0.3: advanced features

### Analytics and Forecasting

- `analyze_device_telemetry(device_id, metric, hours)` performs comprehensive analysis including statistics, trend detection, anomaly identification, and pattern recognition.
- `detect_anomalies(device_id, metric, hours)` uses Z-score and IQR methods to detect spikes, drops, and outliers.
- `forecast_telemetry(device_id, metric, periods)` generates simple linear forecasts with confidence intervals.

### Alerting System

- Create configurable alert rules with conditions: above, below, equals, between, outside, rate_of_change.
- Support for consecutive breach detection and cooldown periods.
- Alert states: active, acknowledged, resolved, silenced.
- Notification channels: webhook, Slack integration.

### Device Grouping

- Create hierarchical device groups for fleet organization.
- Support parent-child relationships and tree visualization.
- Group-based operations and statistics.

### Scheduled Tasks

- Automated device reading, fleet checks, threshold monitoring.
- Configurable intervals or cron-like scheduling.
- Task execution history and status tracking.

### Data Export

- Export to JSON, CSV, Parquet, and Excel formats.
- Summary report generation with statistics.
- Flexible time range and filtering options.

## Example: Advanced Analytics

```json
{"name":"analyze_device_telemetry","arguments":{"device_id":"motor-3","metric":"temperature","hours":24}}
{"name":"detect_anomalies","arguments":{"device_id":"motor-3","metric":"temperature","hours":24}}
{"name":"forecast_telemetry","arguments":{"device_id":"motor-3","metric":"temperature","periods":5}}
```

## Example: Alert Management

```json
{"name":"create_alert_rule","arguments":{"rule_id":"temp-high","name":"High Temperature","metric":"temperature","condition":"above","threshold_value":45,"severity":"warning"}}
{"name":"get_active_alerts","arguments":{}}
{"name":"get_alert_statistics","arguments":{}}
```

## Example: Device Groups

```json
{"name":"create_device_group","arguments":{"group_id":"motors","name":"Motor Group","description":"All motor devices"}}
{"name":"add_device_to_group","arguments":{"device_id":"motor-3","group_id":"motors"}}
{"name":"get_group_hierarchy","arguments":{}}
```

## Boundaries before customer deployment

Use one operator-managed process and separate database/OS account per customer. Company/role configuration is not end-user authentication: anyone who controls the process environment or local database can change/read it. SQL scoping is defense in depth, not a security boundary against the host operator.

This version has no remote MCP endpoint, OAuth, user accounts, billing, dashboard, background polling, ERP dispatch, machine control, or OPC UA implementation. Audit records are local and not tamper-proof. Timestamps/quality are checked, but incoming measurements still depend on a trusted, calibrated gateway. Historical freshness flags describe collection time.

Keep physical protection and emergency interlocks in certified device/PLC systems. For a live pilot, obtain the asset owner's authorization, have a qualified electrical/controls professional provision telemetry access, and test on staging equipment before deployment.

## Project files

| Path | Responsibility |
|---|---|
| `src/electrical_mcp/server.py` | MCP tools, resources, prompt, configuration |
| `src/electrical_mcp/models.py` | Typed device and reading contracts |
| `src/electrical_mcp/connectors.py` | Simulator and HTTP gateway adapter |
| `src/electrical_mcp/service.py` | Permissions and telemetry workflow |
| `src/electrical_mcp/store.py` | SQLite history, drafts, audit, and advanced features |
| `src/electrical_mcp/analytics.py` | Advanced telemetry analytics and forecasting |
| `src/electrical_mcp/alerts.py` | Alerting system with configurable rules |
| `src/electrical_mcp/export.py` | Data export capabilities |
| `src/electrical_mcp/device_groups.py` | Device grouping and hierarchy |
| `src/electrical_mcp/scheduler.py` | Scheduled task management |
| `src/electrical_mcp/websocket.py` | WebSocket real-time monitoring |
| `src/electrical_mcp/mqtt_connector.py` | MQTT IoT device integration |
| `examples/` | Local gateway, sample config, advanced demo |
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
