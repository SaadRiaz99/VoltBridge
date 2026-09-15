"""Exercise v0.4 tools using simulated data and an isolated temporary database."""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory)/'devices.json'
        config.write_text(json.dumps({'devices':[{'id':'motor-3','name':'Simulated motor'}]}))
        params = StdioServerParameters(command=sys.executable, args=['-m','electrical_mcp.server'], env={
            **os.environ, 'EEMCP_CONFIG':str(config), 'EEMCP_DB':str(Path(directory)/'demo.db'),
            'EEMCP_COMPANY':'isolated-demo', 'EEMCP_ROLE':'maintenance'})
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                print('Tools:',len((await session.list_tools()).tools))
                async def call(name, args):
                    result = await session.call_tool(name,args)
                    if result.isError:
                        raise RuntimeError(result.content)
                    value = json.loads(result.content[0].text)
                    print(name, json.dumps(value,indent=2))
                    return value
                await call('read_measurements',{'device_id':'motor-3'})
                await call('get_latest_measurements',{'device_id':'motor-3'})
                await call('get_data_quality_report',{'device_id':'motor-3',
                    'start':'2020-01-01T00:00:00Z','end':'2100-01-01T00:00:00Z'})
                draft = await call('create_maintenance_request_draft',{'device_id':'motor-3',
                    'issue':'Demo inspection','idempotency_key':'demo'})
                await call('get_maintenance_request_draft',{'draft_id':draft['id']})
                await call('create_alert_rule',{'rule_id':'warm','name':'Demo high temperature',
                    'metric':'temperature','condition':'above','threshold_value':45})
                await call('evaluate_device_alerts',{'device_id':'motor-3'})

if __name__ == '__main__':
    asyncio.run(main())
