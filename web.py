import os
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import HTMLResponse

from core import chat_once, new_history, RUNTIME
from session_store import SQLiteMessageHistoryStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage MCP runtime lifecycle on startup and shutdown."""
    await RUNTIME.start()
    yield
    await RUNTIME.aclose()


app = FastAPI(title="Darel Chatbot", version="0.1.0", lifespan=lifespan)

# Enable CORS for external frontends (React, Vue, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific origins in production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_STORE = SQLiteMessageHistoryStore(os.getenv("SESSION_DB_PATH", "sessions.db"))


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str


class SessionInfo(BaseModel):
    session_id: str
    updated_at: float


class SessionListResponse(BaseModel):
    sessions: List[SessionInfo]


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[dict]


@app.get("/", response_class=HTMLResponse)
def index():
    return (
        "<!doctype html><meta charset=utf-8><title>Darel Chat</title>"
        "<style>"
        "body{font-family:sans-serif;margin:0;background:#f7f7f7}"
        "#layout{display:flex;gap:16px;max-width:1100px;margin:24px auto;padding:0 16px}"
        "#sessions{width:280px;background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px;height:80vh;overflow:auto}"
        "#sessionList{margin-top:10px}"
        ".session{padding:8px;border-radius:6px;cursor:pointer}"
        ".session:hover{background:#f0f0f0}"
        ".session.active{background:#e9f0ff}"
        ".session-head{display:flex;gap:8px;align-items:center;justify-content:space-between}"
        ".session-actions{display:flex;gap:8px}"
        "button{padding:6px 10px;font-size:12px}"
        "#chat{flex:1}"
        "#log{white-space:pre-wrap;background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px;height:68vh;overflow:auto}"
        "input{width:100%;padding:10px;font-size:16px;margin-top:10px;border:1px solid #ccc;border-radius:6px}"
        "</style>"
        "<div id=layout>"
        "<div id=sessions>"
        "<div class=session-head>"
        "<div><strong>Sessions</strong></div>"
        "<div class=session-actions>"
        "<button id=refresh>Refresh</button>"
        "<button id=new>New</button>"
        "</div>"
        "</div>"
        "<div id=sessionList></div>"
        "</div>"
        "<div id=chat>"
        "<div id=log></div><input id=msg placeholder='Ask about products…' autofocus>"
        "</div>"
        "</div>"
        "<script>"
        "const log=document.getElementById('log');"
        "const sessionList=document.getElementById('sessionList');"
        "let sid=localStorage.getItem('sid')||'';"
        "function labelFromType(t){if(t==='human')return 'you';if(t==='ai')return 'ai';if(t==='system')return 'system';return t||'msg';}"
        "function textFromContent(c){if(typeof c==='string')return c;try{return JSON.stringify(c);}catch(e){return String(c);}}"
        "function add(who,text){log.textContent+=who+': '+text+'\\n\\n';log.scrollTop=log.scrollHeight;}"
        "async function loadSessions(){"
        "const r=await fetch('/sessions?limit=50');"
        "const j=await r.json();"
        "sessionList.innerHTML='';"
        "j.sessions.forEach(s=>{"
        "const row=document.createElement('div');"
        "row.className='session'+(s.session_id===sid?' active':'');"
        "const ts=new Date(s.updated_at*1000).toLocaleString();"
        "row.textContent=s.session_id.slice(0,8)+' • '+ts;"
        "row.onclick=()=>loadSession(s.session_id);"
        "sessionList.appendChild(row);"
        "});"
        "}"
        "async function loadSession(id){"
        "const r=await fetch('/sessions/'+id);"
        "const j=await r.json();"
        "sid=j.session_id;localStorage.setItem('sid',sid);"
        "log.textContent='';"
        "(j.messages||[]).forEach(m=>{"
        "const who=labelFromType(m.type);"
        "const content=(m.data&&m.data.content!==undefined)?m.data.content:m;"
        "add(who,textFromContent(content));"
        "});"
        "loadSessions();"
        "}"
        "document.getElementById('refresh').addEventListener('click',loadSessions);"
        "document.getElementById('new').addEventListener('click',()=>{sid='';localStorage.removeItem('sid');log.textContent='';loadSessions();});"
        "document.getElementById('msg').addEventListener('keydown',async(e)=>{"
        "if(e.key!=='Enter')return;const m=e.target.value.trim();if(!m)return;"
        "e.target.value='';add('you',m);"
        "const r=await fetch('/chat',{method:'POST',headers:{'content-type':'application/json'},"
        "body:JSON.stringify({session_id:sid,message:m})});"
        "const j=await r.json();sid=j.session_id;localStorage.setItem('sid',sid);add('ai',j.response);"
        "loadSessions();"
        "});"
        "loadSessions();"
        "</script>"
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    session_id = req.session_id or uuid.uuid4().hex
    history = await SESSION_STORE.get_or_create(session_id, new_history)
    try:
        history = await chat_once(history, req.message)
        await SESSION_STORE.set(session_id, history)
        return ChatResponse(session_id=session_id, response=str(history[-1].content))
    except Exception as e:
        return ChatResponse(session_id=session_id, response=f"ERROR: {e}")


@app.get("/sessions", response_model=SessionListResponse)
async def list_sessions(limit: int = 100, offset: int = 0) -> SessionListResponse:
    rows = await SESSION_STORE.list_sessions(limit=limit, offset=offset)
    sessions = [SessionInfo(session_id=sid, updated_at=updated_at) for sid, updated_at in rows]
    return SessionListResponse(sessions=sessions)


@app.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
async def get_session(session_id: str) -> SessionHistoryResponse:
    messages = await SESSION_STORE.get_serialized(session_id)
    return SessionHistoryResponse(session_id=session_id, messages=messages or [])
