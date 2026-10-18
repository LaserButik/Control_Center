import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    url = "http://localhost:8000/sse"
    # نفس المفتاح الموجود في السيرفر
    headers = {"Authorization": "Bearer default_super_secret_key_123"}
    
    print("⏳ Connecting to MCP Server via SSE...")
    
    try:
        async with sse_client(url, headers=headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("✅ Connected & Initialized successfully!")

                tools_response = await session.list_tools()
                print("\n🛠️ Available Tools:")
                for tool in tools_response.tools:
                    print(f" - {tool.name}")

                print("\n🚀 Calling 'get_funnel_stats'...")
                result = await session.call_tool("get_funnel_stats", arguments={})
                print(f"📊 Result: {result.content}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())