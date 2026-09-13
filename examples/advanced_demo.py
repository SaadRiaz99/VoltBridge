"""Advanced demo showcasing new VoltBridge features including analytics, alerting, and scheduling."""
import asyncio
import json
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    """Demonstrate advanced VoltBridge features."""
    print("=== VoltBridge Advanced Features Demo ===\n")

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "electrical_mcp.server"],
        env=dict(os.environ)
    )

    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            # List available tools
            inventory = await session.list_tools()
            print(f"Available tools ({len(inventory.tools)}):")
            for tool in inventory.tools:
                print(f"  - {tool.name}")
            print()

            # 1. Basic device read
            print("1. Reading device telemetry...")
            result = await session.call_tool("read_measurements", {"device_id": "motor-3"})
            if not result.isError:
                reading = json.loads(result.content[0].text)
                print(f"   Motor-3 readings: {len(reading['readings'])} metrics")
                for r in reading['readings']:
                    print(f"   - {r['metric']}: {r['value']} {r['unit']}")
            print()

            # 2. Advanced Analytics
            print("2. Running advanced analytics...")
            result = await session.call_tool("analyze_device_telemetry", {
                "device_id": "motor-3",
                "metric": "temperature",
                "hours": 24
            })
            if not result.isError:
                analysis = json.loads(result.content[0].text)
                print(f"   Trend direction: {analysis.get('trend', {}).get('direction', 'N/A')}")
                print(f"   Anomalies detected: {analysis.get('anomaly_count', 0)}")
            print()

            # 3. Create Alert Rule
            print("3. Creating alert rule for temperature...")
            result = await session.call_tool("create_alert_rule", {
                "rule_id": "temp-high",
                "name": "High Temperature Alert",
                "metric": "temperature",
                "condition": "above",
                "threshold_value": 45,
                "severity": "warning"
            })
            if not result.isError:
                print("   Alert rule created successfully")
            print()

            # 4. Create Device Group
            print("4. Creating device group...")
            result = await session.call_tool("create_device_group", {
                "group_id": "motors",
                "name": "Motor Group",
                "description": "All motor devices"
            })
            if not result.isError:
                print("   Device group created successfully")

            result = await session.call_tool("add_device_to_group", {
                "device_id": "motor-3",
                "group_id": "motors"
            })
            if not result.isError:
                print("   Motor-3 added to group")
            print()

            # 5. Create Scheduled Task
            print("5. Creating scheduled monitoring task...")
            result = await session.call_tool("create_scheduled_task", {
                "task_id": "monitor-motor-3",
                "name": "Monitor Motor 3",
                "task_type": "device_read",
                "interval_seconds": 300,
                "config": {"device_id": "motor-3"}
            })
            if not result.isError:
                task = json.loads(result.content[0].text)
                print(f"   Task created, next run: {task.get('next_run', 'N/A')}")
            print()

            # 6. Export Data
            print("6. Exporting device data...")
            result = await session.call_tool("export_device_data", {
                "device_id": "motor-3",
                "format": "json",
                "hours": 24
            })
            if not result.isError:
                export = json.loads(result.content[0].text)
                print(f"   Exported {export.get('record_count', 0)} records")
            print()

            # 7. Generate Report
            print("7. Generating device report...")
            result = await session.call_tool("generate_device_report", {
                "device_id": "motor-3",
                "hours": 24
            })
            if not result.isError:
                report = json.loads(result.content[0].text)
                print(f"   Report generated with {report.get('total_readings', 0)} readings")
                metrics = report.get('metrics_summary', {})
                for metric, stats in metrics.items():
                    print(f"   - {metric}: min={stats.get('min')}, max={stats.get('max')}, mean={stats.get('mean'):.2f}")
            print()

            # 8. Get Alert Statistics
            print("8. Alert system statistics...")
            result = await session.call_tool("get_alert_statistics", {})
            if not result.isError:
                stats = json.loads(result.content[0].text)
                print(f"   Active alerts: {stats.get('active_count', 0)}")
                print(f"   Rules configured: {stats.get('rules_configured', 0)}")
            print()

            # 9. Get Group Hierarchy
            print("9. Device group hierarchy...")
            result = await session.call_tool("get_group_hierarchy", {})
            if not result.isError:
                hierarchy = json.loads(result.content[0].text)
                print(f"   Total groups: {hierarchy.get('total_groups', 0)}")
            print()

            print("=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
