"""Connect to the actual MCP stdio transport; no LLM API key required."""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "electrical_mcp.server"])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            inventory = await session.list_tools()
            print("Tools:", [tool.name for tool in inventory.tools])
            for name, args in [
                ("read_measurements", {"device_id": "motor-3"}),
                ("check_threshold", {"device_id": "motor-3", "metric": "temperature", "maximum": 45, "unit": "degC"}),
                ("create_maintenance_request_draft", {"device_id": "motor-3", "issue": "Demo: inspect temperature above configured limit", "idempotency_key": "demo-motor-3-inspection"})
            ]:
                result = await session.call_tool(name, args)
                print(name, result.model_dump_json(indent=2))
                if result.isError:
                    raise RuntimeError("MCP tool failed")

if __name__ == "__main__":
    asyncio.run(main())
