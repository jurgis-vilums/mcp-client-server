import os
import sys
import warnings
from contextlib import ExitStack
from typing import List

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

SERVER_PARAMS = StdioServerParameters(command="python", args=["mcp_server.py"])

SYSTEM_PROMPT = (
    "You are a helpful shopping assistant for darel.lv.\n"
    "When the user asks about products, call the tool `darel_search` to look up items.\n"
    "Reply concisely; include names, prices, and URLs when useful."
)

def new_history() -> List[BaseMessage]:
    return [SystemMessage(content=SYSTEM_PROMPT)]


async def chat_once(history: List[BaseMessage], user_text: str) -> List[BaseMessage]:
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=".*create_react_agent has been moved.*",
    )

    model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    with ExitStack() as stack:
        errlog = sys.stderr
        errlog_path = os.getenv("MCP_ERRLOG_PATH")
        if errlog_path:
            errlog = stack.enter_context(open(errlog_path, "a", encoding="utf-8", buffering=1))

        async with stdio_client(SERVER_PARAMS, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
                agent = create_react_agent(model, tools)
                result = await agent.ainvoke({"messages": [*history, HumanMessage(content=user_text)]})
                return result["messages"]
