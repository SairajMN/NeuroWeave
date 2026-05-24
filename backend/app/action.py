import os
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .schemas import ToolAction, ToolResult

# Dynamic path to mcp_server.py
SERVER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server.py"))

async def execute_mcp_tool(action: ToolAction) -> ToolResult:
    """
    Spawns the local FastMCP server in a subprocess, initializes an MCP Stdio session,
    executes the requested tool, and returns a validated ToolResult.
    """
    server_params = StdioServerParameters(
        command="python3",
        args=[SERVER_PATH],
        env=os.environ.copy()
    )
    
    try:
        # Connect to the FastMCP server via stdio transport
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # 1. Initialize the MCP session
                await session.initialize()
                
                # 2. Call the tool with the provided arguments
                result = await session.call_tool(action.name, action.arguments)
                
                # 3. Concatenate the text content blocks returned by the tool
                output_text = ""
                if hasattr(result, "content") and result.content:
                    for block in result.content:
                        if hasattr(block, "text"):
                            output_text += block.text
                        elif isinstance(block, dict) and "text" in block:
                            output_text += block["text"]
                        else:
                            output_text += str(block)
                else:
                    output_text = str(result)
                
                return ToolResult(
                    tool_name=action.name,
                    success=True,
                    output=output_text
                )
                
    except Exception as e:
        return ToolResult(
            tool_name=action.name,
            success=False,
            output="",
            error=f"MCP Tool Execution Failure: {str(e)}"
        )
