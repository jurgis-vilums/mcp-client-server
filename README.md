# Minimal MCP server + client

One MCP tool: `darel_search(query, results_per_page=10, cookie=None)` which calls `darel.lv` search and returns only the `products` list.

## Setup

`pip install -r requirements.txt`

## Config

- Copy `.env.example` to `.env` and fill `OPENAI_API_KEY`.
- Optional: set `DAREL_COOKIE` if Cloudflare blocks requests.

## Run

- CLI chatbot (spawns MCP server automatically): `python mcp_client.py`
- Web chatbot: `uvicorn app:app --reload --port 8000` then open `http://127.0.0.1:8000/`
