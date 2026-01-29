import asyncio
from langchain_mcp_adapters import MultiServerMCPClient
import os

async def main():
    server_config = {
        "gdoc_server": {
            "command": "python",
            "args": [os.path.join(os.path.dirname(__file__), "MCP Server", "gdoc_server.py")],
            "cwd": os.path.join(os.path.dirname(__file__), "MCP Server"),
        }
    }
    
    client = MultiServerMCPClient(server_config)
    
    async with client:
        print("Connected to MCP server(s)")
        print("=" * 70)
        
        async with client.session("gdoc_server") as session:
            tools_list = await session.list_tools()
            print(f"Available tools (via MCP tools/list): {len(tools_list.tools)}")
            for tool in tools_list.tools:
                print(f"  - {tool.name}: {tool.description}")
        
        print("=" * 70)
        
        tools = await client.get_tools()
        if tools:
            print(f"\nLangChain tools available: {len(tools)}")
            search_tool = next((t for t in tools if t.name == "search_insurance_docs"), None)
            if search_tool:
                print("\nTesting search_insurance_docs tool...")
                result = await search_tool.ainvoke({"query": "coverage"})
                print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
