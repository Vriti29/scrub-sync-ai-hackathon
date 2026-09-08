from __future__ import annotations

import html as html_lib
import re
from typing import Any
from urllib.parse import quote_plus

import aiohttp

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = html_lib.unescape(_TAG.sub(" ", text or ""))
    return _WS.sub(" ", text).strip()


async def web_search(query: str, *, limit: int = 5) -> dict[str, Any]:
    """
    Lightweight open-web lookup for live or current facts.
    Prefers Google News RSS, then DuckDuckGo Lite, then Wikipedia.
    """
    cleaned = " ".join(query.split())[:200]
    if not cleaned:
        return {"query": query, "ok": False, "summary": "", "results": []}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    summary = ""
    results: list[dict[str, str]] = []
    timeout = aiohttp.ClientTimeout(total=12)

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        # 1) Google News RSS — strong for scores / current events.
        try:
            news_url = (
                "https://news.google.com/rss/search?"
                f"q={quote_plus(cleaned)}&hl=en-IN&gl=IN&ceid=IN:en"
            )
            async with session.get(news_url) as response:
                if response.status == 200:
                    xml = await response.text()
                    titles = re.findall(r"<title>(.*?)</title>", xml, flags=re.I | re.S)
                    # First title is usually the feed title; skip thin/generic labels.
                    for title in titles[1:]:
                        item = _clean(title)
                        if len(item) < 12:
                            continue
                        if item.lower() in {"google news", "news", "top stories"}:
                            continue
                        if all(item != existing["title"] for existing in results):
                            results.append({"title": item[:220], "url": ""})
                        if len(results) >= limit:
                            break
                    if results:
                        summary = results[0]["title"]
        except Exception:
            pass

        # 2) DuckDuckGo Lite HTML results.
        if len(results) < 2:
            try:
                lite_url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(cleaned)}"
                async with session.get(lite_url) as response:
                    if response.status == 200:
                        page = await response.text()
                        # Lite results are often in <a rel="nofollow" ...>title</a>
                        anchors = re.findall(
                            r'<a[^>]+rel="nofollow"[^>]*>(.*?)</a>',
                            page,
                            flags=re.I | re.S,
                        )
                        for raw in anchors:
                            item = _clean(raw)
                            if len(item) < 8:
                                continue
                            if all(item != existing["title"] for existing in results):
                                results.append({"title": item[:220], "url": ""})
                            if len(results) >= limit:
                                break
                        if not summary and results:
                            summary = results[0]["title"]
            except Exception:
                pass

        # 3) Wikipedia summary fallback for evergreen knowledge.
        if not results:
            try:
                wiki_search = (
                    "https://en.wikipedia.org/w/api.php"
                    f"?action=opensearch&search={quote_plus(cleaned)}"
                    "&limit=1&namespace=0&format=json"
                )
                async with session.get(wiki_search) as response:
                    if response.status == 200:
                        payload = await response.json(content_type=None)
                        titles = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
                        if titles:
                            title = titles[0]
                            summary_url = (
                                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                                + quote_plus(title.replace(" ", "_"))
                            )
                            async with session.get(summary_url) as summary_response:
                                if summary_response.status == 200:
                                    data = await summary_response.json(content_type=None)
                                    extract = _clean(str(data.get("extract") or ""))
                                    if extract:
                                        summary = extract[:800]
                                        results.append(
                                            {
                                                "title": extract[:220],
                                                "url": str(data.get("content_urls", {})
                                                    .get("desktop", {})
                                                    .get("page", ""))[:300],
                                            }
                                        )
            except Exception:
                pass

    return {
        "query": cleaned,
        "ok": bool(summary or results),
        "summary": summary[:800],
        "results": results[:limit],
    }
