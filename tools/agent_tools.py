"""Tool definitions used by Operational and Research agents."""

from __future__ import annotations

import json

import structlog

log = structlog.get_logger(__name__)


###############################################################################
# Research agent tools (Agent-2 style)
#
#
###############################################################################
async def search_web_ddg(query: str) -> str:
    """
    Search the web using DuckDuckGo HTML (no API key).
    Returns JSON: {results: [{title,url,snippet}], count: N} or {error,...}
    """
    try:
        import re
        import urllib.parse
        import httpx
        from bs4 import BeautifulSoup
        import json

        q = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:

            resp = await c.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )

            html = resp.text or ""

        soup = BeautifulSoup(html, "html.parser")

        results = []

        # DuckDuckGo result links
        links = soup.select("a.result__a")

        for a in links[:8]:
            title = a.get_text(strip=True)
            href = a.get("href", "")

            # Try to find snippet near the parent container
            snippet = ""

            parent = a.find_parent("div")
            if parent:
                snippet_tag = parent.select_one(".result__snippet")
                if snippet_tag:
                    snippet = snippet_tag.get_text(" ", strip=True)

            # Clean redirect URLs
            if href.startswith("//duckduckgo.com/l/?"):
                uddg = re.search(r"uddg=([^&]+)", href)
                if uddg:
                    href = urllib.parse.unquote(uddg.group(1))

            if href and href.startswith("http") and title:
                results.append(
                    {
                        "title": title,
                        "url": href,
                        "snippet": snippet[:300],
                    }
                )

        if not results:
            return json.dumps(
                {
                    "error": "No results parsed from DuckDuckGo HTML",
                    "results": [],
                    "raw_length": len(html),
                }
            )

        return json.dumps(
            {
                "results": results,
                "count": len(results),
            }
        )

    except Exception as exc:
        return json.dumps(
            {
                "error": str(exc),
                "results": [],
            }
        )


async def search_arxiv(query: str) -> str:
    """
    Search ArXiv for relevant papers (no API key).
    Returns JSON: {papers: [...], count: N} or {error,...}
    """
    try:
        import urllib.parse
        import xml.etree.ElementTree as ET
        import httpx
        import json

        q = urllib.parse.quote_plus(query)
        url = f"http://export.arxiv.org/api/query?search_query=all:{q}&max_results=5&sortBy=relevance"

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:

            resp = await c.get(
                url,
                headers={"User-Agent": "ResearchAgent/2.0"},
            )

            xml_text = resp.text or ""

        ns = {"a": "http://www.w3.org/2005/Atom"}

        try:
            root = ET.fromstring(xml_text)
        except Exception as parse_err:
            raise

        papers = []
        entries = root.findall("a:entry", ns)

        for i, entry in enumerate(entries[:5]):
            title = (entry.findtext("a:title", "", ns) or "").strip().replace("\n", " ")
            summary = (
                (entry.findtext("a:summary", "", ns) or "")
                .strip()
                .replace("\n", " ")[:350]
            )

            pid = entry.findtext("a:id", "", ns)
            pub = entry.findtext("a:published", "", ns)
            year = pub[:4] if pub else ""

            authors = [
                a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)
            ][:3]

            if title and pid:
                papers.append(
                    {
                        "title": title,
                        "authors": authors,
                        "abstract": summary,
                        "url": pid,
                        "year": year,
                    }
                )

        return json.dumps({"papers": papers, "count": len(papers)})

    except Exception as exc:

        return json.dumps(
            {
                "error": str(exc),
                "papers": [],
                "count": 0,
            }
        )


async def search_semantic_scholar(query: str) -> str:
    """Semantic Scholar search."""
    try:
        import httpx

        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": 8,
            "fields": "title,year,authors,url,abstract,tldr,externalIds",
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
            resp = await c.get(
                url, params=params, headers={"User-Agent": "ResearchAgent/2.0"}
            )
            data = resp.json()

        papers = []
        for p in (data or {}).get("data", []) or []:
            title = (p or {}).get("title")
            if not title:
                continue
            authors = [
                a.get("name")
                for a in (p.get("authors") or [])[:4]
                if isinstance(a, dict)
            ]
            tldr = (
                (p.get("tldr") or {}).get("text")
                if isinstance(p.get("tldr"), dict)
                else None
            )
            papers.append(
                {
                    "title": title,
                    "authors": authors,
                    "year": p.get("year"),
                    "abstract": (p.get("abstract") or "")[:400],
                    "tldr": tldr,
                    "url": p.get("url"),
                    "external_ids": p.get("externalIds"),
                }
            )

        return json.dumps({"papers": papers, "count": len(papers)})
    except Exception as exc:
        return json.dumps({"error": str(exc), "papers": []})


async def search_openalex(query: str) -> str:
    """OpenAlex works search ."""
    try:
        import httpx

        url = "https://api.openalex.org/works"
        params = {"search": query, "per-page": 8}
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
            resp = await c.get(
                url, params=params, headers={"User-Agent": "ResearchAgent/2.0"}
            )
            data = resp.json()

        works = []
        for w in (data or {}).get("results", []) or []:
            title = (w or {}).get("title")
            if not title:
                continue
            works.append(
                {
                    "title": title,
                    "year": w.get("publication_year"),
                    "url": w.get("id"),
                    "doi": (w.get("doi") or ""),
                    "host_venue": (
                        (w.get("host_venue") or {}).get("display_name")
                        if isinstance(w.get("host_venue"), dict)
                        else None
                    ),
                }
            )

        return json.dumps({"works": works, "count": len(works)})
    except Exception as exc:
        return json.dumps({"error": str(exc), "works": []})


async def search_crossref(query: str) -> str:
    """Crossref works search"""
    try:
        import httpx

        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": 8}
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
            resp = await c.get(
                url, params=params, headers={"User-Agent": "ResearchAgent/2.0"}
            )
            data = resp.json()

        items = []
        for it in (((data or {}).get("message") or {}).get("items") or [])[:8]:
            title = (it.get("title") or [""])[0]
            if not title:
                continue
            items.append(
                {
                    "title": title,
                    "year": (
                        (
                            it.get("published-print")
                            or it.get("published-online")
                            or {}
                        ).get("date-parts")
                        or [[None]]
                    )[0][0],
                    "url": it.get("URL"),
                    "doi": it.get("DOI"),
                    "type": it.get("type"),
                }
            )

        return json.dumps({"items": items, "count": len(items)})
    except Exception as exc:
        return json.dumps({"error": str(exc), "items": []})


async def search_osti(query: str) -> str:
    """OSTI.gov records search."""
    try:
        import httpx

        url = "https://www.osti.gov/api/v1/records"
        params = {"q": query, "page": 0, "size": 8}
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
            resp = await c.get(
                url, params=params, headers={"User-Agent": "ResearchAgent/2.0"}
            )
            data = resp.json()

        records = []
        for r in (data or {}).get("records", []) or []:
            title = r.get("title")
            if not title:
                continue
            records.append(
                {
                    "title": title,
                    "year": (
                        r.get("publication_date", "")[:4]
                        if r.get("publication_date")
                        else None
                    ),
                    "url": r.get("product_nsti_url")
                    or r.get("osti_id")
                    or r.get("doi")
                    or r.get("landing_page_url"),
                    "doi": r.get("doi"),
                }
            )

        return json.dumps({"records": records, "count": len(records)})
    except Exception as exc:
        return json.dumps({"error": str(exc), "records": []})
