import asyncio
import math
from statistics import fmean
from datetime import datetime, timezone
from .connectors import SimulatorConnector, HttpConnector, DeviceUnavailable
from .models import Settings, UNITS
from .store import Store

class Operations:
    def __init__(self, settings: Settings, connectors=None):
        self.settings = settings
        self.devices = {d.id: d for d in settings.devices}
        self.store = Store(settings.database)
        self.connectors = connectors or {"simulator": SimulatorConnector(), "http": HttpConnector()}

    def record(self, action, device="", outcome="success"):
        self.store.audit(self.settings.company_id, self.settings.role, action, device, outcome)

    def device(self, device_id):
        if device_id not in self.devices:
            self.record("device_lookup", device_id[:64], "denied")
            raise ValueError("Unknown or inaccessible device")
        return self.devices[device_id]

    def require(self, roles, action, device=""):
        if self.settings.role not in roles:
            self.record(action, device, "denied")
            raise PermissionError("This process role cannot perform that operation")

    def list_devices(self):
        self.record("list_devices")
        return [{"id": d.id, "name": d.name, "connector": d.connector,
                 "simulated": d.connector == "simulator"} for d in self.devices.values()]

    def capabilities(self, device_id):
        device = self.device(device_id)
        self.record("get_device_capabilities", device_id)
        return {"device_id": device.id, "read_only": True, "connector": device.connector,
                "supported_metric_schema": UNITS, "actual_metrics": "Determined by gateway response",
                "physical_control": False}

    async def read(self, device_id):
        device = self.device(device_id)
        try:
            readings = await self.connectors[device.connector].read(device)
        except DeviceUnavailable:
            self.record("read_measurements", device_id, "failed")
            raise
        now = datetime.now(timezone.utc)
        output = []
        for reading in readings:
            age = (now - reading.timestamp).total_seconds()
            stale = age > device.stale_after_seconds
            future = age < -5
            output.append({**reading.model_dump(mode="json"),
                "timestamp": reading.timestamp.isoformat(),
                "stale": stale, "future_timestamp": future,
                "usable": not stale and not future and reading.quality == "good",
                "simulated": reading.simulated or device.connector == "simulator"})
        self.store.save_readings(self.settings.company_id, device_id, output)
        self.record("read_measurements", device_id)
        return {"device_id": device_id, "readings": output}

    async def status(self, device_id):
        self.device(device_id)
        try:
            data = await self.read(device_id)
            return {"device_id": device_id, "status": "online" if all(r["usable"] for r in data["readings"]) else "degraded",
                    "simulated": any(r["simulated"] for r in data["readings"])}
        except DeviceUnavailable:
            return {"device_id": device_id, "status": "unavailable", "message": "Gateway read failed"}

    async def threshold(self, device_id, metric, maximum, unit):
        if metric not in UNITS or unit != UNITS[metric] or not math.isfinite(maximum):
            raise ValueError("Provide a supported metric, matching unit and finite maximum")
        data = await self.read(device_id)
        reading = next((r for r in data["readings"] if r["metric"] == metric), None)
        if reading is None:
            raise ValueError("Device did not return that metric")
        result = "unknown" if not reading["usable"] else ("above_limit" if reading["value"] > maximum else "within_limit")
        return {"device_id": device_id, "result": result, "maximum": maximum, "reading": reading,
                "note": "User-supplied threshold comparison; not a fault diagnosis or safety certification"}

    def history(self, device_id, start, end, limit=100):
        self.device(device_id)
        dates = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in (start, end)]
        if any(d.tzinfo is None for d in dates) or dates[0] > dates[1] or not 1 <= limit <= 500:
            raise ValueError("Use timezone-aware ordered dates and limit 1..500")
        self.record("get_measurement_history", device_id)
        return self.store.history(self.settings.company_id, device_id,
            *(d.astimezone(timezone.utc).isoformat() for d in dates), limit)

    def draft(self, device_id, issue, idempotency_key):
        self.require({"maintenance", "admin"}, "create_maintenance_request_draft", device_id)
        self.device(device_id)
        if not 1 <= len(issue.strip()) <= 2000 or not 1 <= len(idempotency_key.strip()) <= 100:
            raise ValueError("Issue must be 1..2000 characters and key 1..100 characters")
        result = self.store.draft(self.settings.company_id, device_id, issue.strip(), idempotency_key.strip())
        self.record("create_maintenance_request_draft", device_id)
        return result

    def drafts(self, limit=50):
        self.require({"maintenance", "admin"}, "list_maintenance_drafts")
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be 1..100")
        self.record("list_maintenance_drafts")
        return self.store.list_drafts(self.settings.company_id, limit)

    def audit(self, limit=50):
        self.require({"admin"}, "get_audit_events")
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be 1..100")
        self.record("get_audit_events")
        return self.store.audit_events(self.settings.company_id, limit)

    async def fleet_health(self, limit=20):
        if not 1 <= limit <= 50:
            raise ValueError("Limit must be 1..50")
        selected = sorted(self.devices)[:limit]
        semaphore = asyncio.Semaphore(4)

        async def check(device_id):
            async with semaphore:
                return await self.status(device_id)

        devices = await asyncio.gather(*(check(device_id) for device_id in selected))
        self.record("get_fleet_health")
        return {"company_id": self.settings.company_id, "devices": devices,
                "counts": {state: sum(d["status"] == state for d in devices)
                           for state in ("online", "degraded", "unavailable")},
                "checked": len(devices), "total_configured": len(self.devices),
                "truncated": len(selected) < len(self.devices),
                "note": "Gateway reachability and telemetry quality, not equipment safety or fault diagnosis"}

    def measurement_statistics(self, device_id, metric, start, end, limit=500):
        self.device(device_id)
        if metric not in UNITS or not 1 <= limit <= 500:
            raise ValueError("Use a supported metric and limit 1..500")
        dates = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in (start, end)]
        if any(d.tzinfo is None for d in dates) or dates[0] > dates[1]:
            raise ValueError("Use timezone-aware ordered dates")
        rows = self.store.metric_history(self.settings.company_id, device_id, metric,
            *(d.astimezone(timezone.utc).isoformat() for d in dates), limit + 1)
        selected = rows[:limit]
        usable = [r for r in selected if r.get("usable") and r["unit"] == UNITS[metric]]
        groups = {}
        for label, simulated in (("simulated", True), ("non_simulated", False)):
            samples = [r for r in usable if bool(r.get("simulated")) == simulated]
            values = [r["value"] for r in samples]
            groups[label] = {"count": len(values), "minimum": min(values) if values else None,
                "maximum": max(values) if values else None, "mean": fmean(values) if values else None,
                "oldest_timestamp": samples[-1]["timestamp"] if samples else None,
                "newest_timestamp": samples[0]["timestamp"] if samples else None}
        self.record("get_measurement_statistics", device_id)
        return {"device_id": device_id, "metric": metric, "unit": UNITS[metric],
                "sample_count": len(selected), "excluded_count": len(selected) - len(usable),
                "truncated": len(rows) > limit, "groups": groups,
                "note": "Newest matching stored samples; quality is evaluated at collection time. "
                        "Arithmetic sample mean, not a time-weighted average or energy-consumption calculation."}

    async def compare_devices(self, first_device_id, second_device_id, metric):
        if metric not in UNITS or first_device_id == second_device_id:
            raise ValueError("Use a supported metric and two different devices")
        # Validate both before any gateway access.
        self.device(first_device_id)
        self.device(second_device_id)

        async def sample(device_id):
            try:
                data = await self.read(device_id)
                reading = next((r for r in data["readings"] if r["metric"] == metric), None)
                if reading is None:
                    return {"device_id": device_id, "status": "metric_missing", "reading": None}
                valid = reading["usable"] and reading["unit"] == UNITS[metric]
                return {"device_id": device_id, "status": "usable" if valid else "unusable", "reading": reading}
            except DeviceUnavailable:
                return {"device_id": device_id, "status": "unavailable", "reading": None}

        samples = await asyncio.gather(sample(first_device_id), sample(second_device_id))
        comparable = all(s["status"] == "usable" for s in samples)
        reason = None if comparable else "A device is unavailable, missing the metric or has unusable telemetry"
        skew = None
        if comparable:
            a, b = (s["reading"] for s in samples)
            skew = abs((datetime.fromisoformat(a["timestamp"]) - datetime.fromisoformat(b["timestamp"])).total_seconds())
            if a["simulated"] != b["simulated"]:
                comparable, reason = False, "Simulated and non-simulated readings cannot be compared"
            elif skew > 5:
                comparable, reason = False, "Acquisition timestamps differ by more than five seconds"
        difference = samples[0]["reading"]["value"] - samples[1]["reading"]["value"] if comparable else None
        self.record("compare_device_measurements")
        return {"metric": metric, "unit": UNITS[metric], "samples": samples,
                "comparable": comparable, "reason": reason, "timestamp_skew_seconds": skew,
                "difference_first_minus_second": difference,
                "note": "Difference only; equipment suitability and operating limits require engineering context"}
