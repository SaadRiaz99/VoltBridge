"""MQTT connector for IoT device integration."""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable
from .models import Device, Reading, UNITS

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False


class MQTTConnector:
    """MQTT-based connector for IoT telemetry devices."""

    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883,
                 username: str | None = None, password: str | None = None,
                 use_tls: bool = False, keepalive: int = 60):
        if not HAS_MQTT:
            raise ImportError(
                "paho-mqtt is required for MQTT support. "
                "Install with: pip install voltbridge-mcp[mqtt]"
            )

        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.keepalive = keepalive
        self._client: mqtt.Client | None = None
        self._connected = False
        self._subscriptions: dict[str, Callable] = {}
        self._latest_readings: dict[str, list[Reading]] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Connect to the MQTT broker."""
        if self._connected:
            return

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if self.username and self.password:
            self._client.username_pw_set(self.username, self.password)
        if self.use_tls:
            self._client.tls_set()

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        try:
            self._client.connect(self.broker_host, self.broker_port, self.keepalive)
            self._client.loop_start()
            self._connected = True
        except Exception as e:
            raise RuntimeError(f"Failed to connect to MQTT broker: {e}")

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, rc: Any, properties: Any = None) -> None:
        """Callback when connected to broker."""
        self._connected = True

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Callback when message received."""
        try:
            payload = json.loads(msg.payload.decode())
            device_id = payload.get("device_id") or msg.topic.split("/")[-2]
            readings = self._parse_readings(payload)
            if readings:
                self._latest_readings[device_id] = readings
        except Exception:
            pass

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, flags: Any = None, rc: Any = None, properties: Any = None) -> None:
        """Callback when disconnected."""
        self._connected = False

    def _parse_readings(self, payload: dict[str, Any]) -> list[Reading]:
        """Parse MQTT payload into Reading objects."""
        readings = []
        now = datetime.now(timezone.utc)

        if "readings" in payload and isinstance(payload["readings"], list):
            for item in payload["readings"]:
                try:
                    metric = item.get("metric")
                    if metric not in UNITS:
                        continue

                    timestamp_str = item.get("timestamp")
                    if timestamp_str:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    else:
                        timestamp = now

                    reading = Reading(
                        metric=metric,
                        value=float(item["value"]),
                        unit=UNITS[metric],
                        timestamp=timestamp,
                        quality=item.get("quality", "good"),
                        simulated=False,
                    )
                    readings.append(reading)
                except (ValueError, KeyError, TypeError):
                    continue
        else:
            # Single reading format
            for metric, value in payload.items():
                if metric in UNITS and isinstance(value, (int, float)):
                    reading = Reading(
                        metric=metric,
                        value=float(value),
                        unit=UNITS[metric],
                        timestamp=now,
                        quality="good",
                        simulated=False,
                    )
                    readings.append(reading)

        return readings

    def subscribe_device(self, device_id: str, topic_pattern: str = "sensors/{device_id}/telemetry") -> None:
        """Subscribe to a device's MQTT topic."""
        if not self._client:
            raise RuntimeError("Not connected to MQTT broker")

        topic = topic_pattern.format(device_id=device_id)
        self._client.subscribe(topic)

    async def read(self, device: Device) -> list[Reading]:
        """Read the latest readings from MQTT cache."""
        if not self._connected:
            raise RuntimeError("Not connected to MQTT broker")

        # Subscribe if not already
        self.subscribe_device(device.id)

        # Wait briefly for data
        for _ in range(10):
            if device.id in self._latest_readings:
                return self._latest_readings[device.id]
            await asyncio.sleep(0.1)

        # Return empty if no data received
        return []

    async def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False

    def get_status(self) -> dict[str, Any]:
        """Get MQTT connection status."""
        return {
            "connected": self._connected,
            "broker": f"{self.broker_host}:{self.broker_port}",
            "cached_devices": list(self._latest_readings.keys()),
            "subscriptions": list(self._subscriptions.keys()),
        }


class MQTTDeviceManager:
    """Manages MQTT device subscriptions and message routing."""

    def __init__(self, connector: MQTTConnector):
        self.connector = connector
        self._device_configs: dict[str, dict[str, Any]] = {}

    def register_device(self, device_id: str, topic: str, metrics: list[str] | None = None) -> None:
        """Register a device with its MQTT topic configuration."""
        self._device_configs[device_id] = {
            "topic": topic,
            "metrics": metrics or list(UNITS.keys()),
        }
        self.connector.subscribe_device(device_id, topic)

    def unregister_device(self, device_id: str) -> None:
        """Unregister a device."""
        self._device_configs.pop(device_id, None)

    async def publish_command(self, device_id: str, command: dict[str, Any]) -> bool:
        """Publish a command to a device (if supported)."""
        if device_id not in self._device_configs:
            return False

        config = self._device_configs[device_id]
        command_topic = config["topic"].replace("/telemetry", "/command")

        try:
            self.connector._client.publish(command_topic, json.dumps(command))
            return True
        except Exception:
            return False

    def get_device_configs(self) -> dict[str, dict[str, Any]]:
        """Get all registered device configurations."""
        return self._device_configs.copy()
