# Validation record

Verified on September 13, 2026 with Python 3.12.14, MCP SDK 1.30.0 and HTTPX 0.28.1.

`python -m pytest -q`: **26 tests passed**.

Coverage includes real MCP stdio initialization, tool discovery/calls, resources and prompt retrieval; simulated readings and threshold/history flow; duplicate draft retries and conflicting idempotency keys; company-scoped reads; role denials; stale/future/uncertain/bad readings; HTTP response validation, redirects, oversized payloads, bounded network retries and credential transport checks.

HTTP adapter failure tests use HTTPX MockTransport. Physical equipment, live third-party APIs, Windows execution, GitHub Actions and paid customer deployments have not been tested.

`requirements-tested.txt` records the resolved test-environment dependencies, excluding the editable project itself. For a reproducible development setup, install it before `pip install -e . --no-deps`.

Version 0.2 adds tests for fleet partial failures/limits, metric statistics and tenant isolation, excluded/mixed simulated samples, history truncation, comparison validation, offline/missing/stale/skewed readings, and all three new tools over the real MCP stdio transport. Exactly 12 tools are discovered.
