from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

UNITS = {"voltage": "V", "current": "A", "power": "kW", "energy": "kWh", "temperature": "degC"}

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Reading(StrictModel):
    metric: Literal["voltage", "current", "power", "energy", "temperature"]
    value: float = Field(allow_inf_nan=False)
    unit: str
    timestamp: datetime
    quality: Literal["good", "uncertain", "bad"] = "good"
    simulated: bool = False

    @field_validator("timestamp")
    @classmethod
    def aware_timestamp(cls, value):
        if value.tzinfo is None:
            raise ValueError("Reading timestamps must include a timezone")
        return value.astimezone(timezone.utc)

class Device(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=120)
    connector: Literal["simulator", "http"] = "simulator"
    base_url: str | None = None
    token_env: str | None = None
    stale_after_seconds: int = Field(default=120, ge=1, le=86400)

class Settings(StrictModel):
    company_id: str = Field(default="demo-factory", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    role: Literal["viewer", "maintenance", "admin"] = "maintenance"
    database: str = "electrical-mcp.db"
    devices: list[Device] = Field(min_length=1)

    @field_validator("devices")
    @classmethod
    def unique_devices(cls, devices):
        if len({d.id for d in devices}) != len(devices):
            raise ValueError("Device IDs must be unique")
        return devices
