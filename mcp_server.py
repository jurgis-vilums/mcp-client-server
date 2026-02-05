import os
import sys
import time
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP


def debug(msg: str) -> None:
    """Print debug message to stderr (visible in client's console)."""
    print(f"🔧 [MCP SERVER] {msg}", file=sys.stderr, flush=True)


mcp = FastMCP("darel", log_level="ERROR")

DAREL_BASE_URL = "https://darel.lv/"
DAREL_SEARCH_URL = "https://darel.lv/en/module/iqitsearch/searchiqit"
DAREL_COOKIE_TTL_SECONDS = 30 * 60
_darel_cookie_cache: dict[str, Any] = {"expires_at": 0, "cookies": None}

debug("MCP Server module loaded, tool registered")

def _get_darel_cookies() -> list[dict[str, Any]] | None:
    now = time.time()
    cached = _darel_cookie_cache.get("cookies")
    expires_at = _darel_cookie_cache.get("expires_at", 0)
    if cached and expires_at > now:
        debug(f"🍪 Using cached cookies (expires in {int(expires_at - now)}s)")
        return cached
    if cached:
        debug("🍪 Cached cookies expired; refreshing")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        debug(f"⚠️  Playwright import failed: {type(e).__name__}: {e}")
        debug("   Hint: ensure 'playwright' is installed in this environment")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                locale="en-US",
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.goto(DAREL_BASE_URL, wait_until="domcontentloaded", timeout=15000)
            cookies = context.cookies()
            context.close()
            browser.close()
    except Exception as e:
        debug(f"⚠️  Playwright run failed: {type(e).__name__}: {e}")
        msg = str(e).lower()
        if "executable" in msg or "browser" in msg or "chromium" in msg:
            debug("   Hint: install the browser with: python -m playwright install --with-deps chromium")
        if "sandbox" in msg:
            debug("   Hint: Chromium sandbox blocked. Consider running with proper kernel support.")
        return None

    if not cookies:
        debug("⚠️  Playwright returned no cookies")
        return None

    _darel_cookie_cache["cookies"] = cookies
    _darel_cookie_cache["expires_at"] = now + DAREL_COOKIE_TTL_SECONDS
    cookie_names = sorted({c.get("name") for c in cookies if c.get("name")})
    debug(f"🍪 Playwright cookies: {', '.join(cookie_names) if cookie_names else 'none'}")
    if "cf_clearance" in cookie_names:
        debug("   ✅ cf_clearance present")
    else:
        debug("   ⚠️  cf_clearance not present (Cloudflare may still block)")
    return cookies


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

    cookie_arg = cookie
    cookie = cookie or os.getenv("DAREL_COOKIE")
    if cookie:
        headers["cookie"] = cookie
        source = "argument" if cookie_arg else "DAREL_COOKIE env"
        debug(f"   Using cookie for auth ({source})")

    data = {"s": query, "resultsPerPage": str(results_per_page), "ajax": "true"}

    debug("🍪 Fetching Playwright cookies (cached)...")
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        cookies = _get_darel_cookies()
        if cookies:
            for c in cookies:
                name = c.get("name")
                value = c.get("value")
                if not name:
                    continue
                client.cookies.set(
                    name,
                    value,
                    domain=c.get("domain"),
                    path=c.get("path") or "/",
                )
            debug(f"   ✅ Loaded {len(cookies)} cookies from Playwright into client")
        else:
            debug("   ⚠️  No Playwright cookies available")

        try:
            client.get(
                DAREL_BASE_URL,
                headers={
                    "user-agent": headers["user-agent"],
                    "accept-language": headers["accept-language"],
                },
            )
        except httpx.RequestError as e:
            debug(f"⚠️  Cookie priming GET failed: {type(e).__name__}: {e}")

        debug(f"🌐 Making HTTP POST to darel.lv...")
        r = client.post(DAREL_SEARCH_URL, headers=headers, data=data)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError:
            debug(f"❌ HTTP {r.status_code} - {r.text[:200]}")
            debug(
                "   Headers: "
                f"server={r.headers.get('server')}, "
                f"cf-ray={r.headers.get('cf-ray')}, "
                f"cf-cache-status={r.headers.get('cf-cache-status')}, "
                f"set-cookie={'present' if r.headers.get('set-cookie') else 'none'}"
            )
            return []
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
