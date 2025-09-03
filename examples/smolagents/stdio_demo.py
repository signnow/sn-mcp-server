import os
from dotenv import dotenv_values, find_dotenv
from smolagents import ToolCollection, CodeAgent, InferenceClientModel, OpenAIServerModel
from mcp import StdioServerParameters

def main():
    # Модель: провайдеры HF Inference; достаточно задать HF_TOKEN для приватных/гейтед моделей
    model = OpenAIServerModel(
        model_id="gpt-4o-mini",                         # можно "gpt-4o-mini" для дешевле
        api_base="https://api.openai.com/v1",
        api_key=os.environ["OPENAI_API_KEY"],
        # organization="org_...",                  # опционально
        # project="proj_...",                      # опционально
    )

    env_path = find_dotenv(usecwd=True)  # ищет вверх от текущей cwd
    env = dict(os.environ)
    if env_path:
        env.update(dotenv_values(env_path))

    # Поднимаем локальный MCP-сервер через твой CLI (STDIO-режим)
    params = StdioServerParameters(
        command="sn-mcp",
        args=["serve"],            # это твоя команда MCP(stdio)
        env=env            # пробрасываем ENV
    )

    # Важно: trust_remote_code=True только если доверяешь серверу/инструментам
    with ToolCollection.from_mcp(params, trust_remote_code=True) as tcoll:
        agent = CodeAgent(
            model=model,
            tools=[*tcoll.tools],  # все инструменты MCP-сервера доступны агенту
            add_base_tools=False,  # отключаем базовые инструменты smolagents
            max_steps=8,
        )
        print(agent.run("Show me list of templates and its names"))

if __name__ == "__main__":
    main()

    # python examples/smolagents/stdio_demo.py