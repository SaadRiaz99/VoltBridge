"""Connectors return validated telemetry, never execute machine commands."""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlsplit
import httpx
from .models import Device, Reading, UNITS

class DeviceUnavailable(RuntimeError):
    pass

class Connector(Protocol):
    async def read(self, device: Device) -> list[Reading]: ...

class SimulatorConnector:
    async def read(self, device: Device) -> list[Reading]:
        now = datetime.now(timezone.utc)
        values = {"voltage": 230.0, "current": 10.0, "power": 2.1,
                  "energy": 1250.0, "temperature": 48.0}
        return [Reading(metric=m, value=v, unit=UNITS[m], timestamp=now)
                for m, v in values.items()]

class HttpConnector:
    """Admin-configured gateway only; no tool accepts arbitrary URLs."""
    def __init__(self, transport=None):
        self.transport = transport

    async def read(self, device: Device) -> list[Reading]:
        base = device.base_url or ""
        parsed = urlsplit(base)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise DeviceUnavailable("Invalid configured gateway URL")
        headers = {}
        if device.token_env:
            token = os.environ.get(device.token_env)
            if not token:
                raise DeviceUnavailable("Gateway credential is missing")
            if parsed.scheme != "https":
                raise DeviceUnavailable("Token-authenticated gateways require HTTPS")
            headers["Authorization"] = "Bearer " + token
        url = base.rstrip("/") + "/devices/" + device.id + "/measurements"
        async with httpx.AsyncClient(timeout=5, follow_redirects=False,
                                     trust_env=False, transport=self.transport) as client:
            for attempt in range(2):
                try:
                    async with client.stream("GET", url, headers=headers) as response:
                        response.raise_for_status()
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            raw.extend(chunk)
                            if len(raw) > 65536:
                                raise DeviceUnavailable("Gateway response exceeds 64 KiB")
                    payload = json.loads(raw)
                    if not isinstance(payload, dict) or set(payload) != {"readings"}:
                        raise ValueError("Invalid gateway envelope")
                    if not isinstance(payload["readings"], list) or not 1 <= len(payload["readings"]) <= 100:
                        raise ValueError("Invalid readings count")
                    readings = [Reading.model_validate(item) for item in payload["readings"]]
                    if len({r.metric for r in readings}) != len(readings):
                        raise ValueError("Duplicate metrics")
                    if any(r.unit != UNITS[r.metric] for r in readings):
                        raise ValueError("Unexpected unit")
                    return readings
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt == 0:
                        await asyncio.sleep(0.1)
                        continue
                    raise DeviceUnavailable("Gateway unavailable after two attempts") from None
                except (httpx.HTTPError, ValueError):
                    raise DeviceUnavailable("Gateway returned an unsuccessful or invalid response") from None
        raise DeviceUnavailable("Gateway unavailable")
