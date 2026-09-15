"""Advanced alerting system with configurable thresholds and notifications."""
import asyncio
import math
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
from collections import defaultdict


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertCondition(Enum):
    ABOVE = "above"
    BELOW = "below"
    EQUALS = "equals"
    BETWEEN = "between"
    OUTSIDE = "outside"
    RATE_OF_CHANGE = "rate_of_change"
    ANOMALY = "anomaly"
    DEVICE_OFFLINE = "device_offline"


class AlertState(Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SILENCED = "silenced"


@dataclass
class AlertRule:
    """Configuration for an alert rule."""
    rule_id: str
    name: str
    metric: str
    condition: AlertCondition
    description: str = ""
    device_id: str | None = None
    threshold_value: float | None = None
    threshold_value_upper: float | None = None
    severity: AlertSeverity = AlertSeverity.WARNING
    enabled: bool = True
    cooldown_seconds: int = 300
    consecutive_breaches: int = 1
    notification_channels: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """Represents an active or historical alert."""
    alert_id: str
    rule_id: str
    rule_name: str
    device_id: str
    metric: str
    severity: AlertSeverity
    state: AlertState
    message: str
    current_value: float
    threshold_value: float | None
    triggered_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    acknowledged_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationChannel:
    """Configuration for a notification channel."""
    channel_id: str
    channel_type: str  # webhook, email, sms, slack
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    severity_filter: list[AlertSeverity] = field(default_factory=lambda: list(AlertSeverity))


class AlertManager:
    """Manages alert rules, evaluates conditions, and handles notifications."""

    def __init__(self, store=None, company_id="demo-factory"):
        self._rules: dict[str, AlertRule] = {}
        self._active_alerts: dict[str, Alert] = {}
        self._alert_history: list[Alert] = []
        self._notification_channels: dict[str, NotificationChannel] = {}
        self._breach_counts: dict[str, int] = defaultdict(int)
        self._last_alert_time: dict[str, datetime] = {}
        self._store = store
        self._company_id = company_id
        self._evaluation_callbacks: list[Callable] = []
        self._max_history = 1000
        if self._store:
            for data in self._store.get_alert_rules(self._company_id):
                data["condition"] = AlertCondition(data["condition"])
                data["severity"] = AlertSeverity(data["severity"])
                rule = AlertRule(**data)
                self._rules[rule.rule_id] = rule
            for data in reversed(self._store.get_alerts(self._company_id, limit=self._max_history)):
                data["state"] = AlertState(data["state"])
                data["severity"] = AlertSeverity(data["severity"])
                for key in ("triggered_at", "acknowledged_at", "resolved_at"):
                    data[key] = datetime.fromisoformat(data[key]) if data[key] else None
                alert = Alert(**data)
                self._alert_history.append(alert)
                self._last_alert_time[(alert.rule_id, alert.device_id)] = alert.triggered_at
                if alert.state != AlertState.RESOLVED:
                    self._active_alerts[alert.alert_id] = alert

    def _save_rules(self):
        if self._store:
            self._store.save_alert_rules(self._company_id,
                [{**asdict(r), "condition": r.condition.value, "severity": r.severity.value}
                 for r in self._rules.values()])

    def _save_alert(self, alert):
        if self._store:
            data = {**asdict(alert), "state": alert.state.value, "severity": alert.severity.value}
            for key in ("triggered_at", "acknowledged_at", "resolved_at"):
                data[key] = data[key].isoformat() if data[key] else None
            self._store.save_alert(self._company_id, data)

    def add_rule(self, rule: AlertRule) -> None:
        """Add or update an alert rule."""
        from .models import UNITS
        if rule.metric not in UNITS or rule.condition not in {
                AlertCondition.ABOVE, AlertCondition.BELOW, AlertCondition.EQUALS,
                AlertCondition.BETWEEN, AlertCondition.OUTSIDE}:
            raise ValueError("Use a supported metric and threshold condition")
        if rule.threshold_value is None or not math.isfinite(rule.threshold_value):
            raise ValueError("A finite threshold is required")
        if rule.condition in {AlertCondition.BETWEEN, AlertCondition.OUTSIDE}:
            if (rule.threshold_value_upper is None or not math.isfinite(rule.threshold_value_upper)
                    or rule.threshold_value_upper < rule.threshold_value):
                raise ValueError("Provide ordered finite lower and upper thresholds")
        if not 0 <= rule.cooldown_seconds <= 86400 or rule.consecutive_breaches < 1:
            raise ValueError("Invalid cooldown or breach count")
        self._rules[rule.rule_id] = rule
        self._save_rules()

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        removed = self._rules.pop(rule_id, None) is not None
        self._save_rules()
        return removed

    def get_rule(self, rule_id: str) -> AlertRule | None:
        """Get an alert rule by ID."""
        return self._rules.get(rule_id)

    def list_rules(self, device_id: str | None = None, enabled_only: bool = False) -> list[AlertRule]:
        """List alert rules, optionally filtered by device and enabled status."""
        rules = list(self._rules.values())
        if device_id:
            rules = [r for r in rules if r.device_id is None or r.device_id == device_id]
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules

    def add_notification_channel(self, channel: NotificationChannel) -> None:
        """Add or update a notification channel."""
        self._notification_channels[channel.channel_id] = channel

    def remove_notification_channel(self, channel_id: str) -> bool:
        """Remove a notification channel."""
        return self._notification_channels.pop(channel_id, None) is not None

    def evaluate_rules(self, device_id: str, readings: list[dict[str, Any]]) -> list[Alert]:
        """Evaluate all applicable rules against device readings."""
        new_alerts = []
        now = datetime.now(timezone.utc)

        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if rule.device_id is not None and rule.device_id != device_id:
                continue

            # Find the relevant reading
            reading = next((r for r in readings if r.get("metric") == rule.metric), None)
            if reading is None or not reading.get("usable", False):
                continue

            current_value = reading.get("value")
            if current_value is None:
                continue

            # Check cooldown
            rule_key = (rule.rule_id, device_id)
            last_time = self._last_alert_time.get(rule_key)
            if last_time and (now - last_time).total_seconds() < rule.cooldown_seconds:
                continue

            # Evaluate condition
            breached = self._evaluate_condition(rule, current_value)

            if breached:
                self._breach_counts[rule_key] += 1
                if self._breach_counts[rule_key] >= rule.consecutive_breaches:
                    alert = self._create_alert(rule, device_id, current_value, now)
                    alert.metadata.update({"simulated": bool(reading.get("simulated")),
                                           "timestamp": reading.get("timestamp"), "unit": reading.get("unit")})
                    self._save_alert(alert)
                    new_alerts.append(alert)
                    self._active_alerts[alert.alert_id] = alert
                    self._alert_history.append(alert)
                    self._last_alert_time[rule_key] = now
                    self._breach_counts[rule_key] = 0

                    # Trim history if needed
                    if len(self._alert_history) > self._max_history:
                        self._alert_history = self._alert_history[-self._max_history:]
            else:
                self._breach_counts[rule_key] = 0

        return new_alerts

    def _evaluate_condition(self, rule: AlertRule, value: float) -> bool:
        """Evaluate an alert condition against a value."""
        if rule.condition == AlertCondition.ABOVE:
            return rule.threshold_value is not None and value > rule.threshold_value
        elif rule.condition == AlertCondition.BELOW:
            return rule.threshold_value is not None and value < rule.threshold_value
        elif rule.condition == AlertCondition.EQUALS:
            return rule.threshold_value is not None and abs(value - rule.threshold_value) < 1e-6
        elif rule.condition == AlertCondition.BETWEEN:
            if rule.threshold_value is not None and rule.threshold_value_upper is not None:
                return rule.threshold_value <= value <= rule.threshold_value_upper
        elif rule.condition == AlertCondition.OUTSIDE:
            if rule.threshold_value is not None and rule.threshold_value_upper is not None:
                return value < rule.threshold_value or value > rule.threshold_value_upper
        elif rule.condition == AlertCondition.RATE_OF_CHANGE:
            # Simplified rate of change - would need historical data for proper calculation
            return rule.threshold_value is not None and abs(value) > rule.threshold_value
        return False

    def _create_alert(self, rule: AlertRule, device_id: str, current_value: float, timestamp: datetime) -> Alert:
        """Create a new alert from a rule breach."""
        alert_id = f"alert-{uuid.uuid4()}"

        message = f"{rule.name}: {rule.metric} is {current_value}"
        if rule.threshold_value is not None:
            message += f" (threshold: {rule.condition.value} {rule.threshold_value})"

        return Alert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            rule_name=rule.name,
            device_id=device_id,
            metric=rule.metric,
            severity=rule.severity,
            state=AlertState.ACTIVE,
            message=message,
            current_value=current_value,
            threshold_value=rule.threshold_value,
            triggered_at=timestamp,
            metadata={"tags": rule.tags.copy()},
        )

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an active alert."""
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.state = AlertState.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = acknowledged_by
            self._save_alert(alert)
            return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active or acknowledged alert."""
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.state = AlertState.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc)
            self._save_alert(alert)
            del self._active_alerts[alert_id]
            return True
        return False

    def silence_alert(self, alert_id: str, duration_seconds: int = 3600) -> bool:
        """Silence an alert for a specified duration."""
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.state = AlertState.SILENCED
            alert.metadata["silence_until"] = (
                datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
            ).isoformat()
            return True
        return False

    def get_active_alerts(self, severity: AlertSeverity | None = None,
                          device_id: str | None = None) -> list[Alert]:
        """Get active alerts with optional filtering."""
        alerts = list(self._active_alerts.values())
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if device_id:
            alerts = [a for a in alerts if a.device_id == device_id]
        return alerts

    def get_alert_history(self, limit: int = 100, hours: int = 24) -> list[Alert]:
        """Get historical alerts from the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        alerts = [a for a in self._alert_history if a.triggered_at >= cutoff]
        return alerts[-limit:]

    def get_alert_statistics(self) -> dict[str, Any]:
        """Get alert statistics summary."""
        active = self.get_active_alerts()
        history = self.get_alert_history(hours=24)

        severity_counts = defaultdict(int)
        for alert in active:
            severity_counts[alert.severity.value] += 1

        return {
            "active_count": len(active),
            "total_24h": len(history),
            "severity_distribution": dict(severity_counts),
            "rules_configured": len(self._rules),
            "rules_enabled": sum(1 for r in self._rules.values() if r.enabled),
            "notification_channels": len(self._notification_channels),
        }

    async def send_notifications(self, alerts: list[Alert]) -> dict[str, bool]:
        """Send notifications for new alerts through configured channels."""
        results = {}

        for alert in alerts:
            for channel_id, channel in self._notification_channels.items():
                if not channel.enabled:
                    continue
                if alert.severity not in channel.severity_filter:
                    continue

                try:
                    success = await self._send_notification(channel, alert)
                    results[f"{alert.alert_id}:{channel_id}"] = success
                except Exception:
                    results[f"{alert.alert_id}:{channel_id}"] = False

        return results

    async def _send_notification(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send a single notification through a channel."""
        if channel.channel_type == "webhook":
            return await self._send_webhook(channel, alert)
        elif channel.channel_type == "slack":
            return await self._send_slack(channel, alert)
        # Add more channel types as needed
        return False

    async def _send_webhook(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send webhook notification."""
        import httpx

        payload = {
            "alert_id": alert.alert_id,
            "severity": alert.severity.value,
            "device_id": alert.device_id,
            "metric": alert.metric,
            "message": alert.message,
            "current_value": alert.current_value,
            "threshold_value": alert.threshold_value,
            "triggered_at": alert.triggered_at.isoformat(),
        }

        url = channel.config.get("url")
        if not url:
            return False

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            return response.status_code < 400

    async def _send_slack(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send Slack notification."""
        import httpx

        webhook_url = channel.config.get("webhook_url")
        if not webhook_url:
            return False

        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.CRITICAL: "#ff0000",
            AlertSeverity.EMERGENCY: "#9b0000",
        }

        payload = {
            "attachments": [{
                "color": color_map.get(alert.severity, "#cccccc"),
                "title": f"Alert: {alert.rule_name}",
                "text": alert.message,
                "fields": [
                    {"title": "Device", "value": alert.device_id, "short": True},
                    {"title": "Metric", "value": alert.metric, "short": True},
                    {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                    {"title": "Value", "value": str(alert.current_value), "short": True},
                ],
                "footer": "VoltBridge Alert System",
                "ts": int(alert.triggered_at.timestamp()),
            }]
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            return response.status_code == 200
