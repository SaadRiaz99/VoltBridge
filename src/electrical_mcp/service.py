import math
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
