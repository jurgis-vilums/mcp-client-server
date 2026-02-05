# MCP Client-Server Architecture

## High-Level Overview

```mermaid
flowchart TB
    subgraph User["👤 User"]
        Terminal["Terminal/CLI"]
    end
    
    subgraph Client["🖥️ MCP Client Process"]
        CLI["cli.py<br/>REPL Loop"]
        Core["core.py<br/>Agent Logic"]
        Runtime["MCPRuntime<br/>Connection Manager"]
        LangChain["LangChain Agent<br/>+ Anthropic"]
    end
    
    subgraph Server["⚙️ MCP Server Process"]
        FastMCP["FastMCP Server"]
        Tool["darel_search()"]
    end
    
    subgraph External["🌐 External"]
        Claude["Anthropic API<br/>Claude Haiku"]
        Darel["darel.lv<br/>Product API"]
    end
    
    Terminal --> CLI
    CLI --> Core
    Core --> Runtime
    Core --> LangChain
    Runtime -->|"stdio<br/>(stdin/stdout)"| FastMCP
    FastMCP --> Tool
    LangChain -->|"HTTPS"| Claude
    Tool -->|"HTTPS"| Darel
```

---

## Detailed Sequence Diagram: Complete Flow

```mermaid
sequenceDiagram
    autonumber
    
    participant U as 👤 User
    participant CLI as cli.py
    participant RT as MCPRuntime
    participant MCP as mcp_server.py<br/>(subprocess)
    participant Core as chat_once()
    participant Agent as LangChain Agent
    participant Claude as Claude API
    participant Darel as darel.lv
    
    Note over CLI,MCP: 🚀 PHASE 1: STARTUP
    
    U->>CLI: python cli.py
    activate CLI
    
    CLI->>RT: RUNTIME = MCPRuntime()
    Note over RT: _stack = None<br/>_session = None<br/>_tools = None<br/>_lock = Lock()
    
    CLI->>RT: await RUNTIME.start()
    activate RT
    
    RT->>RT: Create AsyncExitStack
    
    RT->>MCP: stdio_client(SERVER_PARAMS)<br/>Spawn subprocess
    activate MCP
    Note over MCP: python mcp_server.py<br/>running as child process
    
    MCP-->>RT: (read, write) streams
    
    RT->>MCP: ClientSession(read, write)
    RT->>MCP: session.initialize()
    Note over RT,MCP: 🤝 MCP Protocol Handshake<br/>(capabilities exchange)
    
    MCP-->>RT: Session ready
    
    RT->>MCP: load_mcp_tools(session)
    Note over MCP: FastMCP scans @mcp.tool()<br/>decorated functions
    
    MCP-->>RT: tools = [darel_search]
    Note over RT: ✅ _tools = [Tool]<br/>_session = Session<br/>_stack = Stack
    
    deactivate RT
    
    CLI->>CLI: history = new_history()
    Note over CLI: history = [SystemMessage]
    
    Note over U,Darel: 💬 PHASE 2: CHAT LOOP (repeats)
    
    loop Each user message
        CLI->>U: input("> ")
        U-->>CLI: "Search for laptops"
        
        CLI->>Core: await chat_once(history, user_text)
        activate Core
        
        Core->>RT: await RUNTIME.start()
        Note over RT: Already started → return early
        
        Core->>Core: async with RUNTIME.lock
        Note over Core: Acquire lock<br/>(thread safety)
        
        Core->>Agent: model = ChatAnthropic(...)
        Core->>Agent: agent = create_agent(model, tools)
        
        Core->>Agent: agent.ainvoke({messages})
        activate Agent
        
        Agent->>Claude: POST /v1/messages<br/>[SystemMessage, HumanMessage]
        activate Claude
        
        Note over Claude: 🤔 Claude thinks...<br/>"User wants products,<br/>I should call darel_search"
        
        Claude-->>Agent: AIMessage with tool_call<br/>{name: "darel_search",<br/>args: {query: "laptops"}}
        deactivate Claude
        
        Note over Agent,MCP: 🔧 PHASE 3: TOOL EXECUTION
        
        Agent->>MCP: Execute darel_search("laptops")
        activate MCP
        
        MCP->>Darel: POST /searchiqit<br/>{s: "laptops"}
        activate Darel
        
        Darel-->>MCP: {products: [...]}
        deactivate Darel
        
        MCP->>MCP: Transform to compact format
        
        MCP-->>Agent: [{name, price, url}, ...]
        deactivate MCP
        
        Note over Agent,Claude: 📝 PHASE 4: FINAL RESPONSE
        
        Agent->>Claude: POST /v1/messages<br/>[..., ToolResult]
        activate Claude
        
        Note over Claude: 🤔 Claude formats<br/>products for user
        
        Claude-->>Agent: AIMessage<br/>"Here are laptops..."
        deactivate Claude
        
        Agent-->>Core: result = {messages: [...]}
        deactivate Agent
        
        Core-->>CLI: return messages
        deactivate Core
        
        CLI->>CLI: history = messages
        CLI->>U: print(history[-1].content)
    end
    
    Note over U,Darel: 🛑 PHASE 5: SHUTDOWN
    
    U-->>CLI: (empty input)
    
    CLI->>RT: await RUNTIME.aclose()
    activate RT
    
    RT->>MCP: stack.aclose()
    Note over MCP: Subprocess terminates
    deactivate MCP
    
    RT->>RT: _stack = None<br/>_session = None<br/>_tools = None
    deactivate RT
    
    deactivate CLI
```

---

## State Machine: MCPRuntime

```mermaid
stateDiagram-v2
    [*] --> Uninitialized: __init__()
    
    Uninitialized --> Starting: start() called
    Starting --> Running: subprocess spawned<br/>session initialized<br/>tools loaded
    
    Running --> Running: start() called<br/>(no-op, return early)
    Running --> Closing: aclose() called
    
    Closing --> Uninitialized: stack closed<br/>vars reset to None
    
    Uninitialized --> [*]: program exits
    
    note right of Uninitialized
        _stack = None
        _session = None
        _tools = None
    end note
    
    note right of Running
        _stack = AsyncExitStack
        _session = ClientSession
        _tools = [Tool, ...]
    end note
```

---

## Data Flow: Message Types

```mermaid
flowchart LR
    subgraph Input["📥 Input"]
        UT["User Text<br/>'Search laptops'"]
    end
    
    subgraph Messages["💬 Message Chain"]
        SM["SystemMessage<br/>'You are a shopping<br/>assistant...'"]
        HM["HumanMessage<br/>'Search laptops'"]
        AI1["AIMessage<br/>tool_calls: [{<br/>name: darel_search<br/>args: {query: laptops}<br/>}]"]
        TM["ToolMessage<br/>[{name: ASUS...,<br/>price: €399}]"]
        AI2["AIMessage<br/>'Here are laptops:<br/>1. ASUS - €399...'"]
    end
    
    subgraph Output["📤 Output"]
        Resp["Final Response<br/>to User"]
    end
    
    UT --> HM
    SM --> AI1
    HM --> AI1
    AI1 --> TM
    TM --> AI2
    AI2 --> Resp
```

---

## Component Responsibilities

```mermaid
flowchart TB
    subgraph cli["cli.py"]
        direction TB
        A1["• Entry point"]
        A2["• REPL loop"]
        A3["• Exception handling"]
        A4["• Lifecycle management"]
    end
    
    subgraph core["core.py"]
        direction TB
        B1["• MCPRuntime class"]
        B2["• Connection pooling"]
        B3["• Agent creation"]
        B4["• Claude API calls"]
    end
    
    subgraph mcp_server["mcp_server.py"]
        direction TB
        C1["• FastMCP server"]
        C2["• Tool definitions"]
        C3["• External API calls"]
        C4["• Data transformation"]
    end
    
    cli -->|"imports"| core
    core -->|"spawns<br/>subprocess"| mcp_server
```

---

## IPC: stdio Communication

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant stdin as stdin pipe
    participant stdout as stdout pipe
    participant Server as MCP Server
    
    Note over Client,Server: JSON-RPC over stdio
    
    Client->>stdin: {"jsonrpc":"2.0","method":"initialize",...}
    stdin->>Server: (bytes)
    Server->>stdout: {"jsonrpc":"2.0","result":{capabilities:...}}
    stdout->>Client: (bytes)
    
    Client->>stdin: {"jsonrpc":"2.0","method":"tools/list"}
    stdin->>Server: (bytes)
    Server->>stdout: {"jsonrpc":"2.0","result":{tools:[...]}}
    stdout->>Client: (bytes)
    
    Client->>stdin: {"jsonrpc":"2.0","method":"tools/call",<br/>"params":{"name":"darel_search","arguments":{...}}}
    stdin->>Server: (bytes)
    
    Note over Server: Execute tool function
    
    Server->>stdout: {"jsonrpc":"2.0","result":{content:[...]}}
    stdout->>Client: (bytes)
```

---

## 📦 requirements.txt Analysis

```mermaid
flowchart LR
    subgraph Core["🧠 Core Dependencies"]
        MCP["mcp<br/><i>MCP protocol</i>"]
        Anthropic["langchain-anthropic<br/><i>Claude API wrapper</i>"]
        LangChain["langchain<br/><i>Agent framework</i>"]
        Adapters["langchain-mcp-adapters<br/><i>MCP ↔ LangChain bridge</i>"]
    end
    
    subgraph Utils["🔧 Utilities"]
        Dotenv["python-dotenv<br/><i>.env file loading</i>"]
        HTTPX["httpx<br/><i>HTTP client</i>"]
    end
    
    subgraph Web["🌐 Web Interface"]
        FastAPI["fastapi<br/><i>REST API framework</i>"]
        Uvicorn["uvicorn[standard]<br/><i>ASGI server</i>"]
    end
    
    Adapters --> MCP
    Adapters --> LangChain
    Anthropic --> LangChain
```

| Package | Used In | Purpose |
|---------|---------|---------|
| `httpx` | `mcp_server.py` | HTTP client for external API calls (darel.lv) |
| `mcp` | `core.py`, `mcp_server.py` | MCP protocol (ClientSession, FastMCP server) |
| `python-dotenv` | `core.py` | Load environment variables from `.env` file |
| `langchain` | `core.py` | Agent framework (`create_agent`) |
| `langchain-mcp-adapters` | `core.py` | Bridge MCP tools to LangChain (`load_mcp_tools`) |
| `langchain-anthropic` | `core.py` | Claude API integration (`ChatAnthropic`) |
| `fastapi` | `web.py` | REST API framework for web interface |
| `uvicorn[standard]` | CLI command | ASGI server to run FastAPI |

---

## 🔌 REST API Reference (web.py)

```mermaid
flowchart LR
    subgraph Endpoints["API Endpoints"]
        Chat["POST /chat<br/><i>Send message</i>"]
        ListSessions["GET /sessions<br/><i>List all sessions</i>"]
        GetSession["GET /sessions/{id}<br/><i>Get session history</i>"]
        Docs["GET /docs<br/><i>Swagger UI</i>"]
    end
    
    subgraph Storage["💾 Storage"]
        SQLite["sessions.db<br/><i>SQLite</i>"]
    end
    
    Chat --> SQLite
    ListSessions --> SQLite
    GetSession --> SQLite
```

| Endpoint | Method | Description | Request | Response |
|----------|--------|-------------|---------|----------|
| `/chat` | POST | Send a message to the chatbot | `{message, session_id?}` | `{session_id, response}` |
| `/sessions` | GET | List all sessions | `?limit=100&offset=0` | `{sessions: [{session_id, updated_at}]}` |
| `/sessions/{id}` | GET | Get full conversation history | - | `{session_id, messages: [...]}` |
| `/` | GET | Built-in HTML chat UI | - | HTML |
| `/docs` | GET | Swagger/OpenAPI docs | - | HTML |

### Session Flow

```mermaid
sequenceDiagram
    participant Client as External Frontend
    participant API as web.py
    participant DB as sessions.db
    
    Note over Client,DB: New conversation
    Client->>API: POST /chat {message: "Hi"}
    API->>DB: Create session + save message
    API-->>Client: {session_id: "abc123", response: "Hello!"}
    
    Note over Client,DB: Continue conversation
    Client->>API: POST /chat {message: "Search laptops", session_id: "abc123"}
    API->>DB: Load history, append, save
    API-->>Client: {session_id: "abc123", response: "Here are laptops..."}
    
    Note over Client,DB: List & restore sessions
    Client->>API: GET /sessions?limit=10
    API->>DB: Query recent sessions
    API-->>Client: {sessions: [{session_id, updated_at}, ...]}
    
    Client->>API: GET /sessions/abc123
    API->>DB: Load full history
    API-->>Client: {session_id, messages: [system, human, ai, ...]}
```

---

## File Structure

```
mcp-client-server/
├── cli.py             # 🖥️  Terminal interface (python cli.py)
├── web.py             # 🌐  Web interface (uvicorn web:app)
├── core.py            # 🧠  Shared logic (MCPRuntime, chat_once)
├── mcp_server.py      # ⚙️  MCP tool server
├── session_store.py   # 💾  SQLite session storage
├── sessions.db        # 🗄️  Session database (auto-created)
├── requirements.txt   # 📦  Dependencies
├── .env               # 🔑  API keys (gitignored)
└── .env.example       # 📋  Config template
```
