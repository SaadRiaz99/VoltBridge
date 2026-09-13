"""WebSocket support for real-time telemetry monitoring."""
import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client."""
    client_id: str
    subscribed_devices: set[str] = field(default_factory=set)
    subscribed_metrics: set[str] = field(default_factory=set)
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TelemetryUpdate:
    """Real-time telemetry update message."""
    device_id: str
    readings: list[dict[str, Any]]
    timestamp: str
    alert_level: str | None = None
    anomalies: list[dict[str, Any]] = field(default_factory=list)


class WebSocketManager:
    """Manages WebSocket connections for real-time telemetry streaming."""

    def __init__(self):
        self._clients: dict[str, WebSocketClient] = {}
        self._update_queue: asyncio.Queue[TelemetryUpdate] = asyncio.Queue()
        self._running = False
        self._broadcast_task: asyncio.Task | None = None
        self._callbacks: list[Callable[[TelemetryUpdate], None]] = []

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def register_client(self, client_id: str) -> WebSocketClient:
        """Register a new WebSocket client."""
        client = WebSocketClient(client_id=client_id)
        self._clients[client_id] = client
        return client

    def unregister_client(self, client_id: str) -> None:
        """Remove a WebSocket client."""
        self._clients.pop(client_id, None)

    def subscribe_device(self, client_id: str, device_id: str) -> bool:
        """Subscribe a client to a specific device's updates."""
        if client_id not in self._clients:
            return False
        self._clients[client_id].subscribed_devices.add(device_id)
        return True

    def unsubscribe_device(self, client_id: str, device_id: str) -> bool:
        """Unsubscribe a client from a device's updates."""
        if client_id not in self._clients:
            return False
        self._clients[client_id].subscribed_devices.discard(device_id)
        return True

    def subscribe_metric(self, client_id: str, metric: str) -> bool:
        """Subscribe a client to a specific metric type across all devices."""
        if client_id not in self._clients:
            return False
        self._clients[client_id].subscribed_metrics.add(metric)
        return True

    def unsubscribe_metric(self, client_id: str, metric: str) -> bool:
        """Unsubscribe a client from a metric type."""
        if client_id not in self._clients:
            return False
        self._clients[client_id].subscribed_metrics.discard(metric)
        return True

    def add_callback(self, callback: Callable[[TelemetryUpdate], None]) -> None:
        """Add a callback function to be called when updates are broadcast."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[TelemetryUpdate], None]) -> None:
        """Remove a callback function."""
        self._callbacks = [cb for cb in self._callbacks if cb != callback]

    async def publish_update(self, update: TelemetryUpdate) -> None:
        """Publish a telemetry update to the queue for broadcasting."""
        await self._update_queue.put(update)

    def get_subscribers_for_update(self, update: TelemetryUpdate) -> list[str]:
        """Get client IDs that should receive a specific update."""
        subscribers = []
        for client_id, client in self._clients.items():
            # Check device subscription
            if client.subscribed_devices and update.device_id in client.subscribed_devices:
                subscribers.append(client_id)
                continue

            # Check metric subscription
            if client.subscribed_metrics:
                for reading in update.readings:
                    if reading.get("metric") in client.subscribed_metrics:
                        subscribers.append(client_id)
                        break

            # If no specific subscriptions, client gets all updates
            if not client.subscribed_devices and not client.subscribed_metrics:
                subscribers.append(client_id)

        return subscribers

    async def broadcast_update(self, update: TelemetryUpdate) -> list[str]:
        """Broadcast an update to all subscribed clients. Returns list of notified client IDs."""
        subscribers = self.get_subscribers_for_update(update)
        message = {
            "type": "telemetry_update",
            "device_id": update.device_id,
            "readings": update.readings,
            "timestamp": update.timestamp,
            "alert_level": update.alert_level,
            "anomalies": update.anomalies,
        }

        # Execute callbacks
        for callback in self._callbacks:
            try:
                callback(update)
            except Exception:
                pass

        return subscribers

    async def _broadcast_loop(self) -> None:
        """Internal loop that processes queued updates."""
        while self._running:
            try:
                update = await asyncio.wait_for(self._update_queue.get(), timeout=1.0)
                await self.broadcast_update(update)
            except asyncio.TimeoutError:
                continue
            except Exception:
                await asyncio.sleep(0.1)

    async def start(self) -> None:
        """Start the broadcast loop."""
        if not self._running:
            self._running = True
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def stop(self) -> None:
        """Stop the broadcast loop."""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

    def get_status(self) -> dict[str, Any]:
        """Get current WebSocket manager status."""
        return {
            "active_clients": self.client_count,
            "queue_size": self._update_queue.qsize(),
            "running": self._running,
            "client_subscriptions": {
                client_id: {
                    "devices": list(client.subscribed_devices),
                    "metrics": list(client.subscribed_metrics),
                }
                for client_id, client in self._clients.items()
            },
        }


class RealTimeMonitor:
    """Real-time monitoring engine that periodically reads and publishes updates."""

    def __init__(self, operations, ws_manager: WebSocketManager, interval_seconds: float = 5.0):
        self.operations = operations
        self.ws_manager = ws_manager
        self.interval_seconds = interval_seconds
        self._monitoring_task: asyncio.Task | None = None
        self._running = False
        self._monitored_devices: set[str] = set()
        self._alert_callbacks: list[Callable] = []

    def add_device(self, device_id: str) -> None:
        """Add a device to monitor."""
        self._monitored_devices.add(device_id)

    def remove_device(self, device_id: str) -> None:
        """Remove a device from monitoring."""
        self._monitored_devices.discard(device_id)

    def add_alert_callback(self, callback: Callable) -> None:
        """Add a callback for alert notifications."""
        self._alert_callbacks.append(callback)

    async def _monitoring_loop(self) -> None:
        """Periodically read telemetry and publish updates."""
        while self._running:
            try:
                for device_id in list(self._monitored_devices):
                    try:
                        data = await self.operations.read(device_id)
                        readings = data.get("readings", [])

                        # Check for anomalies
                        anomalies = []
                        alert_level = None
                        for reading in readings:
                            if not reading.get("usable", True):
                                alert_level = "warning"
                            if reading.get("stale", False):
                                alert_level = "critical"
                                anomalies.append({
                                    "type": "stale_reading",
                                    "metric": reading.get("metric"),
                                    "message": "Reading is stale",
                                })

                        update = TelemetryUpdate(
                            device_id=device_id,
                            readings=readings,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            alert_level=alert_level,
                            anomalies=anomalies,
                        )

                        await self.ws_manager.publish_update(update)

                        # Trigger alert callbacks
                        if alert_level:
                            for callback in self._alert_callbacks:
                                try:
                                    await asyncio.coroutine(callback)(update) if asyncio.iscoroutinefunction(callback) else callback(update)
                                except Exception:
                                    pass

                    except Exception:
                        # Device read failed
                        update = TelemetryUpdate(
                            device_id=device_id,
                            readings=[],
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            alert_level="critical",
                            anomalies=[{"type": "device_unavailable", "message": "Failed to read device"}],
                        )
                        await self.ws_manager.publish_update(update)

                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)

    async def start(self, device_ids: list[str] | None = None) -> None:
        """Start monitoring specified devices."""
        if device_ids:
            for device_id in device_ids:
                self._monitored_devices.add(device_id)

        if not self._running:
            self._running = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

    def get_status(self) -> dict[str, Any]:
        """Get monitoring status."""
        return {
            "running": self._running,
            "monitored_devices": list(self._monitored_devices),
            "interval_seconds": self.interval_seconds,
            "ws_manager_status": self.ws_manager.get_status(),
        }
