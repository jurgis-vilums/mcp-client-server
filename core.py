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
        print("\n🔧 [DEBUG] MCPRuntime.__init__() - Creating runtime instance")
        self._stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._tools = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._session is not None:
            print("⏭️  [DEBUG] MCPRuntime.start() - Already started, skipping")
            return

        print("\n🚀 [DEBUG] MCPRuntime.start() - Starting MCP runtime...")
        stack = AsyncExitStack()
        errlog = sys.stderr
        errlog_path = os.getenv("MCP_ERRLOG_PATH")
        if errlog_path:
            errlog = stack.enter_context(
                open(errlog_path, "a", encoding="utf-8", buffering=1)
            )

        print("📡 [DEBUG] Spawning MCP server subprocess (mcp_server.py)...")
        read, write = await stack.enter_async_context(stdio_client(SERVER_PARAMS, errlog=errlog))
        
        print("🤝 [DEBUG] Establishing ClientSession with MCP server...")
        session = await stack.enter_async_context(ClientSession(read, write))
        
        print("🔄 [DEBUG] Initializing session (handshake)...")
        await session.initialize()
        
        print("🔍 [DEBUG] Loading MCP tools from server...")
        tools = await load_mcp_tools(session)
        print(f"✅ [DEBUG] Loaded {len(tools)} tool(s): {[t.name for t in tools]}")

        self._stack = stack
        self._session = session
        self._tools = tools
        print("🎉 [DEBUG] MCP Runtime started successfully!\n")

    async def aclose(self) -> None:
        print("\n🛑 [DEBUG] MCPRuntime.aclose() - Shutting down...")
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None
        self._tools = None
        print("👋 [DEBUG] MCP Runtime closed.\n")

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
    print(f"\n💬 [DEBUG] chat_once() called with: '{user_text}'")
    print(f"📜 [DEBUG] History has {len(history)} message(s)")
    
    await RUNTIME.start()

    async with RUNTIME.lock:
        model_name = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        print(f"\n🤖 [DEBUG] Creating ChatAnthropic model: {model_name}")
        model = ChatAnthropic(model=model_name)
        
        print(f"🔨 [DEBUG] Creating agent with {len(RUNTIME.tools)} tool(s)...")
        agent = create_agent(model, RUNTIME.tools, system_prompt=SYSTEM_PROMPT)
        
        print("📤 [DEBUG] Sending to Claude (agent.ainvoke)...")
        print("   ⏳ Waiting for response (Claude may call tools)...\n")
        result = await agent.ainvoke({"messages": [*history, HumanMessage(content=user_text)]})
        
        messages = result["messages"]
        print(f"\n📥 [DEBUG] Received {len(messages)} message(s) back:")
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            content_preview = str(msg.content)[:80] + "..." if len(str(msg.content)) > 80 else str(msg.content)
            print(f"   [{i}] {msg_type}: {content_preview}")
        
        return messages
