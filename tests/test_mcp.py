import json
import os
import sys
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_stdio_workflow(tmp_path):
    params = StdioServerParameters(command=sys.executable, args=['-m', 'electrical_mcp.server'],
                                  env={**os.environ, 'EEMCP_DB': str(tmp_path/'mcp.db'),
                                       'EEMCP_ROLE': 'maintenance', 'EEMCP_COMPANY': 'test'})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = {tool.name for tool in (await session.list_tools()).tools}
            assert len(tools) == 9
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
