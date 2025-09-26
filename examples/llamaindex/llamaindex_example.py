import asyncio
import os

from dotenv import dotenv_values, find_dotenv
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec


async def main() -> None:
    # Load environment variables (as in your example)
    env_path = find_dotenv(usecwd=True)
    if env_path:
        os.environ.update(dotenv_values(env_path))

    # 1) Start your MCP server as a separate process via STDIO (analog of StdioServerParameters)
    mcp_client = BasicMCPClient("sn-mcp", args=["serve"])  # reads os.environ

    # Alternatives (if remote server is needed):
    # mcp_client = BasicMCPClient("http://host:port/sse")         # SSE
    # mcp_client = BasicMCPClient("https://host/mcp")             # Streamable HTTP

    # 2) Auto-conversion of tools from MCP → FunctionTool (descriptions/JSON schemas will be pulled)
    spec = McpToolSpec(client=mcp_client, include_resources=False)  # allowed_tools=[...] if needed
    tools = await spec.to_tool_list_async()

    # 3) LlamaIndex Agent
    agent = FunctionAgent(
        name="MCP Agent",
        description="Agent with tools from sn-mcp",
        llm=OpenAI(model=os.environ["LLM_MODEL"], api_base=os.environ["LLM_API_HOST"], api_key=os.environ["LLM_KEY"]),
        tools=tools,
        system_prompt="Be helpful.",
    )

    resp = await agent.run("Show me list of templates and its names")
    print(resp)


asyncio.run(main())
