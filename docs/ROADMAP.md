# Development roadmap

## Delivered: v0.1 local integration foundation

Simulator, HTTP gateway reads, typed MCP tools/resources/prompt, local process roles, company-scoped SQLite records, telemetry quality checks, threshold comparisons, maintenance draft idempotency, audit records, examples and tests.

## Stage 1: one real device pilot

Choose a device and obtain its vendor protocol contract. Validate units/scaling and acquisition time against the vendor software. Test network loss and recovery. Define retention, backups and operator provisioning. Acceptance: recorded readings match independently observed readings within the device's documented precision, with no simulated values presented as real.

## Stage 2: one company-software integration

Build an ERP/CMMS adapter against its sandbox. Add a separate human approval interface, an outbox and idempotent dispatch with external ticket IDs. Acceptance: retries produce one external record and unauthorized users cannot approve or dispatch it.

## Stage 3: managed customer deployment

Add authenticated remote MCP transport with scoped identities, per-user permissions, tenant isolation tests, encrypted secrets, external audit retention, backup restore testing and monitoring. Add explicit sampling/retention jobs if continuous history is sold. Acceptance: identity cannot choose another tenant, backup restore works, expired authorization is rejected, and customer support commitments are staffed.

## Stage 4: more protocols and billing

Choose Modbus, MQTT or OPC UA based on actual customer hardware. Add connectors only after mapping and emulator/hardware tests. Add usage metering, customer billing and deployment automation once pilot economics are understood.

Machine control is a separate engineering scope. It requires command allowlists, independent approval and physical/device safety controls; the current server exposes no machine command tools.
