import asyncio
import os

from dotenv import dotenv_values, find_dotenv
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI


async def main() -> None:
    env_path = find_dotenv(usecwd=True)
    if env_path:
        os.environ.update(dotenv_values(env_path))

    # MCP server as subprocess (example: your sn-mcp serve)
    client = MultiServerMCPClient(
        {
            "sn": {
                "transport": "stdio",
                "command": "sn-mcp",
                "args": ["serve"],
                # "cwd": "/path/to/dir",
                # "env": {"VAR": "value"},
                # "allowed_tools": ["list_templates", "get_template"],
            }
        }
    )

    tools = await client.get_tools()  # MCP → LangChain tools

    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_KEY"),
        base_url=os.getenv("LLM_API_HOST"),
        temperature=0,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Be helpful."),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )
    agent = create_openai_tools_agent(llm, tools, prompt)
    execu = AgentExecutor(agent=agent, tools=tools, verbose=True)

    out = await execu.ainvoke({"input": "Show me list of templates and its names"})
    print(out.get("output", out))


asyncio.run(main())
