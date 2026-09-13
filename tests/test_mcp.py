import json
import os
import sys
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_stdio_workflow(tmp_path):
    config = tmp_path/'devices.json'
    config.write_text(json.dumps({'devices': [{'id': d, 'name': d} for d in ['motor-3', 'motor-4']]}))
    params = StdioServerParameters(command=sys.executable, args=['-m', 'electrical_mcp.server'],
                                  env={**os.environ, 'EEMCP_DB': str(tmp_path/'mcp.db'),
                                       'EEMCP_ROLE': 'maintenance', 'EEMCP_COMPANY': 'test', 'EEMCP_CONFIG': str(config)})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = {tool.name for tool in (await session.list_tools()).tools}
            assert len(tools) == 32  # Updated for v0.3 with advanced features
            result = await session.call_tool('read_measurements', {'device_id': 'motor-3'})
            assert not result.isError
            reading = json.loads(result.content[0].text)
            assert reading['readings'][0]['simulated'] is True
            draft_args = {'device_id': 'motor-3', 'issue': 'Inspect bearing', 'idempotency_key': 'mcp-retry'}
            first = await session.call_tool('create_maintenance_request_draft', draft_args)
            second = await session.call_tool('create_maintenance_request_draft', draft_args)
            assert not first.isError and not second.isError
            assert json.loads(first.content[0].text)['id'] == json.loads(second.content[0].text)['id']
            denied = await session.call_tool('get_audit_events', {})
            assert denied.isError
            unknown = await session.call_tool('read_measurements', {'device_id': 'other-company'})
            assert unknown.isError
            assert len((await session.list_resources()).resources) == 2
            assert 'motor-3' in (await session.read_resource('electrical://devices')).contents[0].text
            prompt = await session.get_prompt('investigate_device', {'device_id': 'motor-3'})
            assert prompt.messages
            fleet = await session.call_tool('get_fleet_health', {})
            assert not fleet.isError
            assert json.loads(fleet.content[0].text)['counts']['online'] == 2
            stats = await session.call_tool('get_measurement_statistics', {
                'device_id': 'motor-3', 'metric': 'temperature',
                'start': '2020-01-01T00:00:00Z', 'end': '2100-01-01T00:00:00Z'})
            assert not stats.isError
            assert json.loads(stats.content[0].text)['groups']['simulated']['mean'] == 48
            comparison = await session.call_tool('compare_device_measurements', {
                'first_device_id': 'motor-3', 'second_device_id': 'unknown', 'metric': 'power'})
            assert comparison.isError

            compared = await session.call_tool('compare_device_measurements', {
                'first_device_id': 'motor-3', 'second_device_id': 'motor-4', 'metric': 'power'})
            assert not compared.isError
            assert json.loads(compared.content[0].text)['difference_first_minus_second'] == 0


async def test_advanced_analytics(tmp_path):
    """Test advanced analytics tools."""
    config = tmp_path/'devices.json'
    config.write_text(json.dumps({'devices': [{'id': 'motor-3', 'name': 'motor-3'}]}))
    params = StdioServerParameters(command=sys.executable, args=['-m', 'electrical_mcp.server'],
                                  env={**os.environ, 'EEMCP_DB': str(tmp_path/'mcp.db'),
                                       'EEMCP_ROLE': 'admin', 'EEMCP_COMPANY': 'test', 'EEMCP_CONFIG': str(config)})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            # Test analyze_device_telemetry
            result = await session.call_tool('analyze_device_telemetry', {
                'device_id': 'motor-3', 'metric': 'temperature', 'hours': 24
            })
            assert not result.isError

            # Test detect_anomalies
            result = await session.call_tool('detect_anomalies', {
                'device_id': 'motor-3', 'metric': 'temperature', 'hours': 24
            })
            assert not result.isError

            # Test forecast_telemetry
            result = await session.call_tool('forecast_telemetry', {
                'device_id': 'motor-3', 'metric': 'temperature', 'periods': 5
            })
            assert not result.isError


async def test_alert_management(tmp_path):
    """Test alert management tools."""
    config = tmp_path/'devices.json'
    config.write_text(json.dumps({'devices': [{'id': 'motor-3', 'name': 'motor-3'}]}))
    params = StdioServerParameters(command=sys.executable, args=['-m', 'electrical_mcp.server'],
                                  env={**os.environ, 'EEMCP_DB': str(tmp_path/'mcp.db'),
                                       'EEMCP_ROLE': 'admin', 'EEMCP_COMPANY': 'test', 'EEMCP_CONFIG': str(config)})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            # Create alert rule
            result = await session.call_tool('create_alert_rule', {
                'rule_id': 'temp-high', 'name': 'High Temperature',
                'metric': 'temperature', 'condition': 'above',
                'threshold_value': 45, 'severity': 'warning'
            })
            assert not result.isError

            # List alert rules
            result = await session.call_tool('list_alert_rules', {})
            assert not result.isError

            # Get active alerts
            result = await session.call_tool('get_active_alerts', {})
            assert not result.isError

            # Get alert statistics
            result = await session.call_tool('get_alert_statistics', {})
            assert not result.isError


async def test_device_groups(tmp_path):
    """Test device group tools."""
    config = tmp_path/'devices.json'
    config.write_text(json.dumps({'devices': [{'id': 'motor-3', 'name': 'motor-3'}]}))
    params = StdioServerParameters(command=sys.executable, args=['-m', 'electrical_mcp.server'],
                                  env={**os.environ, 'EEMCP_DB': str(tmp_path/'mcp.db'),
                                       'EEMCP_ROLE': 'admin', 'EEMCP_COMPANY': 'test', 'EEMCP_CONFIG': str(config)})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            # Create device group
            result = await session.call_tool('create_device_group', {
                'group_id': 'motors', 'name': 'Motor Group',
                'description': 'All motor devices'
            })
            assert not result.isError

            # Add device to group
            result = await session.call_tool('add_device_to_group', {
                'device_id': 'motor-3', 'group_id': 'motors'
            })
            assert not result.isError

            # List device groups
            result = await session.call_tool('list_device_groups', {})
            assert not result.isError

            # Get group hierarchy
            result = await session.call_tool('get_group_hierarchy', {})
            assert not result.isError


async def test_scheduled_tasks(tmp_path):
    """Test scheduled task tools."""
    config = tmp_path/'devices.json'
    config.write_text(json.dumps({'devices': [{'id': 'motor-3', 'name': 'motor-3'}]}))
    params = StdioServerParameters(command=sys.executable, args=['-m', 'electrical_mcp.server'],
                                  env={**os.environ, 'EEMCP_DB': str(tmp_path/'mcp.db'),
                                       'EEMCP_ROLE': 'admin', 'EEMCP_COMPANY': 'test', 'EEMCP_CONFIG': str(config)})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            # Create scheduled task
            result = await session.call_tool('create_scheduled_task', {
                'task_id': 'monitor-motor-3', 'name': 'Monitor Motor 3',
                'task_type': 'device_read', 'interval_seconds': 300,
                'config': {'device_id': 'motor-3'}
            })
            assert not result.isError

            # List scheduled tasks
            result = await session.call_tool('list_scheduled_tasks', {})
            assert not result.isError

            # Get task history
            result = await session.call_tool('get_task_history', {'task_id': 'monitor-motor-3'})
            assert not result.isError


async def test_data_export(tmp_path):
    """Test data export tools."""
    config = tmp_path/'devices.json'
    config.write_text(json.dumps({'devices': [{'id': 'motor-3', 'name': 'motor-3'}]}))
    params = StdioServerParameters(command=sys.executable, args=['-m', 'electrical_mcp.server'],
                                  env={**os.environ, 'EEMCP_DB': str(tmp_path/'mcp.db'),
                                       'EEMCP_ROLE': 'maintenance', 'EEMCP_COMPANY': 'test', 'EEMCP_CONFIG': str(config)})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            # Export device data as JSON
            result = await session.call_tool('export_device_data', {
                'device_id': 'motor-3', 'format': 'json', 'hours': 24
            })
            assert not result.isError

            # Export device data as CSV
            result = await session.call_tool('export_device_data', {
                'device_id': 'motor-3', 'format': 'csv', 'hours': 24
            })
            assert not result.isError

            # Generate device report
            result = await session.call_tool('generate_device_report', {
                'device_id': 'motor-3', 'hours': 24
            })
            assert not result.isError
