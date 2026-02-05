# Minimal MCP server + client

## Example: `web.py` `/chat` POST

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for laptops", "session_id": "optional-session-id"}'
```

### Sample Response

```json
{
  "session_id": "abc123",
  "response": "Here are some laptops from darel.lv..."
}
```


## Setup

`pip install -r requirements.txt`

## Config

- Copy `.env.example` to `.env` and fill `ANTHROPIC_API_KEY`.
- Optional: set `ANTHROPIC_MODEL` to use a different Claude model (default: `claude-haiku-4-5-20251001`).
- Optional: set `DAREL_COOKIE` if Cloudflare blocks requests.

## Run either cli of web (both spavns mcp server automatically)

- CLI chatbot: `python cli.py`
- Web chatbot: `uvicorn web:app --reload --port 8000` then open `http://127.0.0.1:8000/`


## File Structure

```
├── cli.py           # 🖥️  Terminal interface
├── web.py           # 🌐  Web interface (FastAPI)
├── core.py          # 🧠  Shared logic (MCPRuntime, chat_once)
├── mcp_server.py    # ⚙️  MCP tool server
└── requirements.txt # 📦  Dependencies
```

## For more in depth undertsanding:
-  ARHITECTURE.MD (use Markdown Preview Mermaid Support extension)
- prompt: "i want you act as a teacher. First get understanding by looking at the codebase, then provide me a intuition on how this codebase works. What is the flow, what is the purpouse of each file. Then, ask questions, to check wether user understood the basics. Continue with harder questions up until user doesnt undertsand something and then provide intuition on that. Dont get locket on single topic, be proactive on covering at least 3 main topics regarding this implementation"
