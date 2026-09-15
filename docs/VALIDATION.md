# VoltBridge v0.4 validation

Verified September 15, 2026 on Python 3.12.14 with MCP SDK 1.30.0 and HTTPX 0.28.1.

`PYTHONPATH=src python -m pytest -q`: **48 passed**. The original upstream suite contained 38 passing tests; this update adds 10 regression tests and expands the real MCP stdio workflow. Exactly **36 tools** are discovered.

Coverage includes cached freshness without gateway access, bounded quality reports, draft permissions/company isolation, nested group reloads, persisted task enums/status, zero thresholds, alert restart/acknowledgment/resolution, device-specific cooldown, corrected between-range semantics, shared gateway concurrency, viewer write denials, chronological forecasts, forecast limits, and execution of all four new tools over MCP.

## Query benchmark

`PYTHONPATH=src python scripts/benchmark_history.py` builds a temporary database of 30,000 synthetic rows and runs 30 repetitions of one metric-history query, returning the same 20 samples before/after adding the metric index.

| Measurement | Median |
|---|---:|
| Baseline index configuration | 4.1137 ms |
| Dedicated metric index | 0.0170 ms |

SQLite's query plan uses `readings_metric_lookup` and no temporary sort. This is a synthetic warm-cache SQL microbenchmark, not end-to-end latency, hardware performance or a customer SLA. Indexes also consume disk space and add write overhead. The script checks identical query results and never touches customer databases.

## Boundaries

Physical equipment, broker/WebSocket deployments, Windows execution, multi-process persistence and live ERP integrations were not tested. MQTT and WebSocket modules remain separate from the MCP entry point. No external notifications were sent. The scheduler loop is not auto-started; configured tasks run through `run_task_now`, and detailed execution history is in memory. Cron and unsupported task/alert conditions now fail explicitly.

The existing `requirements-tested.txt` describes the earlier minimal test environment, not a full lock of all v0.3 optional/declaration additions. Install the current `.[dev]` requirements for development. GitHub Actions results are separate from these local results.
