# Connecting electrical/electronics equipment and software

## Implemented HTTP gateway contract

The administrator configures an exact base URL in `devices.json`. The tool accepts only a registered device ID. For `meter-1`, the adapter sends:

```http
GET /devices/meter-1/measurements
```

Response example (replace the timestamp with the actual acquisition time):

```json
{
  "readings": [
    {
      "metric": "power",
      "value": 3.2,
      "unit": "kW",
      "timestamp": "2026-09-13T12:00:00+00:00",
      "quality": "good",
      "simulated": false
    }
  ]
}
```

Allowed metric/unit pairs: voltage/V, current/A, power/kW, energy/kWh, temperature/degC. Values must be finite. Timestamps need a timezone; timestamps more than five seconds in the future are unusable. Quality is `good`, `uncertain`, or `bad`. The response cannot contain duplicate metrics. It must contain at least one reading and be at most 64 KiB. The simulator emits five fixed illustrative values; it does not model motor physics or accumulate energy.

A configured `token_env` names an environment variable containing the gateway bearer token. Tokens require HTTPS and are never returned by inventory tools. Do not put tokens in JSON, prompts, URLs or Git. Tokenless HTTP is intended for the loopback example or an operator-assessed isolated local network; use HTTPS for real integrations.

A response from an HTTP connector is not automatically proof of real hardware. Demo gateways must set `simulated: true`. The device list describes adapter type; returned readings carry the simulation flag.

## Adding another protocol

1. Implement the `Connector` protocol: `async def read(self, device) -> list[Reading]`.
2. Add a configuration model with only the required operator-managed endpoint fields.
3. Register the new adapter in `Operations` and extend the allowed connector discriminator.
4. Convert device-specific units and register formats to `Reading` at the adapter boundary.
5. Cover disconnects, timeouts, invalid data, timestamps and reconnect behavior with a protocol simulator.
6. Validate against the exact device model and vendor documentation.

| Future adapter | Required information before implementation |
|---|---|
| Modbus TCP/RTU | Device model, register map, function codes, unit ID, scaling, word order, serial/network parameters |
| OPC UA | Endpoint, certificates, node IDs and application/user authorization |
| MQTT | Broker/TLS credentials, topic mapping, payload schema, retained-message freshness |
| ERP/CMMS | Vendor API contract, scoped credentials, sandbox account, draft/approval behavior |

These are extension requirements, not shipped connectors. Do not infer registers or write values into machines without verified vendor mapping.

## Company software integration

Maintenance drafts currently persist in SQLite with `sent_to_external_system: false`. An ERP adapter should use a separate authenticated human approval channel, a transactional outbox, idempotency keys and an external-record ID. Do not claim a draft is delivered until the external system confirms it. Restrict each customer to provisioned endpoints and tenant credentials.

## History semantics

History stores a sample when a tool reads the device. It is not continuous collection. Results are newest first, capped by `limit`. Repeated polling produces repeated samples; there is no time-weighted energy integration. For energy consumed over a period, compare validated cumulative meter readings and handle resets, rollover and gaps before adding a billing/reporting feature.
