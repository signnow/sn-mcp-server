import os

from dotenv import dotenv_values, find_dotenv
from mcp import StdioServerParameters
from smolagents import (
    CodeAgent,
    OpenAIServerModel,
    ToolCollection,
)


def main():
    # Model: HF Inference providers; just set HF_TOKEN for private/gated models
    model = OpenAIServerModel(
        model_id="gpt-4o-mini",  # can use "gpt-4o-mini" for cheaper
        api_base="https://api.openai.com/v1",
        api_key=os.environ["OPENAI_API_KEY"],
        # organization="org_...",                  # optional
        # project="proj_...",                      # optional
    )

    env_path = find_dotenv(usecwd=True)  # searches upward from current cwd
    env = dict(os.environ)
    if env_path:
        env.update(dotenv_values(env_path))

    # Start local MCP server via your CLI (STDIO mode)
    params = StdioServerParameters(command="sn-mcp", args=["serve"], env=env)  # this is your MCP(stdio) command  # pass ENV

    # Important: trust_remote_code=True only if you trust the server/tools
    with ToolCollection.from_mcp(params, trust_remote_code=True) as tcoll:
        agent = CodeAgent(
            model=model,
            tools=[*tcoll.tools],  # all MCP server tools are available to the agent
            add_base_tools=False,  # disable smolagents base tools
            max_steps=8,
        )
        print(agent.run("Show me list of templates and its names"))


if __name__ == "__main__":
    main()

    # python examples/smolagents/stdio_demo.py
