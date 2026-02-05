import os
import sys
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP


def debug(msg: str) -> None:
    """Print debug message to stderr (visible in client's console)."""
    print(f"🔧 [MCP SERVER] {msg}", file=sys.stderr, flush=True)


mcp = FastMCP("darel", log_level="ERROR")

DAREL_BASE_URL = "https://darel.lv/"
DAREL_SEARCH_URL = "https://darel.lv/en/module/iqitsearch/searchiqit"

debug("MCP Server module loaded, tool registered")


@mcp.tool()
def darel_search(query: str, results_per_page: int = 10, cookie: Optional[str] = None) -> list[dict[str, Any]]:
    """Search darel.lv and return a compact list of products (name/price/url/etc)."""
    
    debug(f"═══════════════════════════════════════")
    debug(f"🔍 TOOL CALLED: darel_search")
    debug(f"   query='{query}', results_per_page={results_per_page}")
    debug(f"═══════════════════════════════════════")

    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
        "origin": "https://darel.lv",
        "referer": "https://darel.lv/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36",
        "accept-language": "en-US,en;q=0.9",
    }

    cookie = cookie or os.getenv("DAREL_COOKIE")
    if cookie:
        headers["cookie"] = cookie
        debug("   Using cookie for auth")

    data = {"s": query, "resultsPerPage": str(results_per_page), "ajax": "true"}
    
    debug(f"🌐 Priming cookies with GET {DAREL_BASE_URL} ...")
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        try:
            client.get(
                DAREL_BASE_URL,
                headers={
                    "user-agent": headers["user-agent"],
                    "accept-language": headers["accept-language"],
                },
            )
        except httpx.RequestError:
            pass

        debug(f"🌐 Making HTTP POST to darel.lv...")
        r = client.post(DAREL_SEARCH_URL, headers=headers, data=data)
        r.raise_for_status()
        debug(f"✅ HTTP {r.status_code} - Response received")
        products = r.json().get("products", [])
        debug(f"📦 Raw response has {len(products)} products")

    compact: list[dict[str, Any]] = []
    for p in products:
        if not isinstance(p, dict):
            continue
        compact.append(
            {
                "id_product": p.get("id_product"),
                "name": p.get("name"),
                "price": p.get("price"),
                "url": p.get("url") or p.get("link"),
                "reference": p.get("reference"),
                "manufacturer_name": p.get("manufacturer_name"),
                "category_name": p.get("category_name"),
            }
        )
    
    debug(f"📤 Returning {len(compact)} products to agent")
    if compact:
        debug(f"   First product: {compact[0].get('name', 'N/A')}")
    debug(f"═══════════════════════════════════════\n")
    
    return compact

if __name__ == "__main__":
    mcp.run(transport="stdio")
