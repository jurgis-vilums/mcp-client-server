import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse

from chat import chat_once, new_history

app = FastAPI(title="Darel Chatbot", version="0.1.0")

SESSIONS: Dict[str, List] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str


@app.get("/", response_class=HTMLResponse)
def index():
    return (
        "<!doctype html><meta charset=utf-8><title>Darel Chat</title>"
        "<style>body{font-family:sans-serif;max-width:800px;margin:40px auto}"
        "#log{white-space:pre-wrap;border:1px solid #ddd;padding:12px;height:60vh;overflow:auto}"
        "input{width:100%;padding:10px;font-size:16px;margin-top:10px}</style>"
        "<div id=log></div><input id=msg placeholder='Ask about products…' autofocus>"
        "<script>"
        "const log=document.getElementById('log');"
        "let sid=localStorage.getItem('sid')||'';"
        "function add(who,text){log.textContent+=who+': '+text+'\\n\\n';log.scrollTop=log.scrollHeight;}"
        "document.getElementById('msg').addEventListener('keydown',async(e)=>{"
        "if(e.key!=='Enter')return;const m=e.target.value.trim();if(!m)return;"
        "e.target.value='';add('you',m);"
        "const r=await fetch('/chat',{method:'POST',headers:{'content-type':'application/json'},"
        "body:JSON.stringify({session_id:sid,message:m})});"
        "const j=await r.json();sid=j.session_id;localStorage.setItem('sid',sid);add('ai',j.response);"
        "});</script>"
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    session_id = req.session_id or uuid.uuid4().hex
    history = SESSIONS.get(session_id) or new_history()
    try:
        history = await chat_once(history, req.message)
        SESSIONS[session_id] = history
        return ChatResponse(session_id=session_id, response=str(history[-1].content))
    except Exception as e:
        return ChatResponse(session_id=session_id, response=f"ERROR: {e}")
