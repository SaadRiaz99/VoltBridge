"""Tests for advanced VoltBridge features."""
import json
import sys
import pytest
from datetime import datetime, timezone, timedelta


def test_analytics_module():
    """Test analytics module functionality."""
    from electrical_mcp.analytics import TelemetryAnalytics, analyze_device_history

    analytics = TelemetryAnalytics()

    # Test statistics calculation
    values = [20.0, 22.0, 21.0, 23.0, 25.0, 24.0, 26.0]
    stats = analytics.calculate_statistics(values)
    assert stats["count"] == 7
    assert stats["min"] == 20.0
    assert stats["max"] == 26.0
    assert abs(stats["mean"] - 23.0) < 0.01
    assert stats["std"] > 0

    # Test trend analysis
    trend = analytics.analyze_trend(values)
    assert "direction" in trend
    assert "slope" in trend
    assert "r_squared" in trend
    assert trend["direction"] in ["increasing", "decreasing", "stable", "volatile"]

    # Test anomaly detection
    values_with_anomaly = [20.0, 21.0, 22.0, 50.0, 23.0, 21.0, 20.0]
    anomalies = analytics.detect_anomalies(values_with_anomaly)
    assert len(anomalies) > 0
    assert any("spike" in a["types"] or "outlier" in a["types"] for a in anomalies)

    # Test forecasting
    forecast = analytics.forecast_simple(values, periods=3)
    assert "forecast" in forecast
    assert len(forecast["forecast"]) == 3
    assert "predicted_value" in forecast["forecast"][0]

    # Test pattern detection
    patterns = analytics.detect_patterns(values)
    assert "patterns" in patterns
    assert "statistics" in patterns
    assert "trend" in patterns


def test_analyze_device_history():
    """Test device history analysis."""
    from electrical_mcp.analytics import analyze_device_history

    readings = [
        {"metric": "temperature", "value": 45.0, "unit": "degC", "timestamp": "2024-01-01T00:00:00Z", "usable": True},
        {"metric": "temperature", "value": 46.0, "unit": "degC", "timestamp": "2024-01-01T01:00:00Z", "usable": True},
        {"metric": "temperature", "value": 44.0, "unit": "degC", "timestamp": "2024-01-01T02:00:00Z", "usable": True},
        {"metric": "voltage", "value": 230.0, "unit": "V", "timestamp": "2024-01-01T00:00:00Z", "usable": True},
    ]

    result = analyze_device_history(readings, "temperature")
    assert result["metric"] == "temperature"
    assert result["unit"] == "degC"
    assert result["data_points_analyzed"] == 3
    assert "statistics" in result
    assert "trend" in result
    assert "anomalies" in result


def test_alert_manager():
    """Test alert manager functionality."""
    from electrical_mcp.alerts import AlertManager, AlertRule, AlertSeverity, AlertCondition

    manager = AlertManager()

    # Create alert rule
    rule = AlertRule(
        rule_id="temp-high",
        name="High Temperature",
        metric="temperature",
        condition=AlertCondition.ABOVE,
        threshold_value=45.0,
        severity=AlertSeverity.WARNING,
    )
    manager.add_rule(rule)

    # List rules
    rules = manager.list_rules()
    assert len(rules) == 1
    assert rules[0].rule_id == "temp-high"

    # Evaluate rules
    readings = [{"metric": "temperature", "value": 48.0, "usable": True}]
    alerts = manager.evaluate_rules("motor-3", readings)
    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.WARNING

    # Get active alerts
    active = manager.get_active_alerts()
    assert len(active) == 1

    # Acknowledge alert
    success = manager.acknowledge_alert(alerts[0].alert_id, "operator1")
    assert success

    # Get statistics
    stats = manager.get_alert_statistics()
    assert stats["active_count"] == 1
    assert stats["rules_configured"] == 1


def test_device_group_manager():
    """Test device group manager functionality."""
    from electrical_mcp.device_groups import DeviceGroupManager

    manager = DeviceGroupManager()

    # Create group
    group = manager.create_group("motors", "Motor Group", "All motor devices")
    assert group.group_id == "motors"
    assert group.name == "Motor Group"

    # Add device to group
    success = manager.add_device_to_group("motor-3", "motors")
    assert success

    # List groups
    groups = manager.list_groups()
    assert len(groups) == 1

    # Get group devices
    devices = manager.get_group_devices("motors")
    assert "motor-3" in devices

    # Get device groups
    device_groups = manager.get_device_groups("motor-3")
    assert len(device_groups) == 1
    assert device_groups[0].group_id == "motors"

    # Get hierarchy
    hierarchy = manager.get_group_tree()
    assert hierarchy["total_groups"] == 1


def test_task_scheduler():
    """Test task scheduler functionality."""
    from electrical_mcp.scheduler import TaskScheduler, TaskType

    # Create mock operations
    class MockOps:
        async def read(self, device_id):
            return {"readings": [{"metric": "temperature", "value": 45.0}]}

        async def fleet_health(self, limit=20):
            return {"devices": [], "checked": 0}

    scheduler = TaskScheduler(MockOps())

    # Create task
    task = scheduler.create_task(
        task_id="monitor-motor-3",
        name="Monitor Motor 3",
        task_type=TaskType.DEVICE_READ,
        interval_seconds=300,
        config={"device_id": "motor-3"},
    )
    assert task.task_id == "monitor-motor-3"

    # List tasks
    tasks = scheduler.list_tasks()
    assert len(tasks) == 1

    # Run task
    import asyncio
    execution = asyncio.run(scheduler.run_task_now("monitor-motor-3"))
    assert execution.status.value == "completed"

    # Get history
    history = scheduler.get_task_history("monitor-motor-3")
    assert len(history) == 1


def test_exporter():
    """Test data exporter functionality."""
    from electrical_mcp.export import TelemetryExporter

    exporter = TelemetryExporter()

    # Test JSON export
    data = [
        {"metric": "temperature", "value": 45.0, "unit": "degC"},
        {"metric": "temperature", "value": 46.0, "unit": "degC"},
    ]
    json_output = exporter.export_json(data, pretty=True)
    assert isinstance(json_output, str)
    parsed = json.loads(json_output)
    assert len(parsed) == 2

    # Test CSV export
    csv_output = exporter.export_csv(data)
    assert isinstance(csv_output, str)
    assert "metric" in csv_output
    assert "temperature" in csv_output

    # Test supported formats
    assert "json" in exporter.supported_formats
    assert "csv" in exporter.supported_formats


def test_report_generator():
    """Test report generator functionality."""
    from electrical_mcp.export import TelemetryExporter, ReportGenerator

    exporter = TelemetryExporter()
    generator = ReportGenerator(exporter)

    readings = [
        {"metric": "temperature", "value": 45.0, "unit": "degC", "timestamp": "2024-01-01T00:00:00Z"},
        {"metric": "temperature", "value": 46.0, "unit": "degC", "timestamp": "2024-01-01T01:00:00Z"},
        {"metric": "voltage", "value": 230.0, "unit": "V", "timestamp": "2024-01-01T00:00:00Z"},
    ]

    report = generator.generate_summary_report("motor-3", readings)
    assert report["device_id"] == "motor-3"
    assert report["total_readings"] == 3
    assert "temperature" in report["metrics_summary"]
    assert "voltage" in report["metrics_summary"]
