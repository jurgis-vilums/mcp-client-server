import asyncio
import os
import sys
from pathlib import Path
from contextlib import AsyncExitStack
from typing import List, Optional

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).with_name("mcp_server.py"))],
)

SYSTEM_PROMPT = (
    "You are a helpful shopping assistant for darel.lv.\n"
    "When the user asks about products, call the tool `darel_search` to look up items.\n"
    "Reply concisely; include names, prices, and URLs when useful."
)

class MCPRuntime:
    def __init__(self) -> None:
        self._stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._tools = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._session is not None:
            return

        stack = AsyncExitStack()
        errlog = sys.stderr
        errlog_path = os.getenv("MCP_ERRLOG_PATH")
        if errlog_path:
            errlog = stack.enter_context(
                open(errlog_path, "a", encoding="utf-8", buffering=1)
            )

        read, write = await stack.enter_async_context(stdio_client(SERVER_PARAMS, errlog=errlog))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        tools = await load_mcp_tools(session)

        self._stack = stack
        self._session = session
        self._tools = tools

    async def aclose(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None
        self._tools = None

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    @property
    def tools(self):
        return self._tools


RUNTIME = MCPRuntime()

def new_history() -> List[BaseMessage]:
    return [SystemMessage(content=SYSTEM_PROMPT)]


async def chat_once(history: List[BaseMessage], user_text: str) -> List[BaseMessage]:
    await RUNTIME.start()

    async with RUNTIME.lock:
        model = ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"))
        agent = create_agent(model, RUNTIME.tools, system_prompt=SYSTEM_PROMPT)
        result = await agent.ainvoke({"messages": [*history, HumanMessage(content=user_text)]})
        return result["messages"]
