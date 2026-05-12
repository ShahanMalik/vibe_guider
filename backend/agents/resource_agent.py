"""
resource_agent.py
=================
Discovers relevant external links from public web search results.
The implementation is generic and query-driven, with no site-specific scraping code.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

try:
    from ddgs import DDGS
except ImportError:  # Backward compatibility
    from duckduckgo_search import DDGS


MAX_LINKS = 6


def _is_data_or_model_request(text: str) -> bool:
    haystack = (text or "").lower()
    signals = {
        "dataset",
        "model",
        "train",
        "training",
        "prediction",
        "classification",
        "detection",
        "deepfake",
        "machine learning",
        "ai",
        "computer vision",
    }
    return any(signal in haystack for signal in signals)


def _build_queries(state: dict, is_data_request: bool) -> list[str]:
    base = (state.get("project_summary") or state.get("user_query") or "").strip()
    if not base:
        return []

    queries = [
        f"{base} open source resources",
        f"{base} implementation guide",
    ]

    if is_data_request:
        queries.extend(
            [
                f"{base} public dataset",
                f"{base} benchmark dataset",
            ]
        )

    if state.get("request_mode") == "recommendation_compare":
        queries.append(f"{base} tools comparison")

    seen = set()
    unique = []
    for query in queries:
        key = query.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(query)

    return unique


def _clean_text(value: str, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _hostname(url: str) -> str:
    parsed = urlparse(url or "")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _score_result(title: str, snippet: str, is_data_request: bool) -> int:
    text = f"{title} {snippet}".lower()

    data_terms = ("dataset", "benchmark", "corpus", "data")
    dev_terms = ("github", "documentation", "docs", "tutorial", "example", "guide")

    score = 0
    if is_data_request:
        score += sum(2 for term in data_terms if term in text)
    score += sum(1 for term in dev_terms if term in text)

    return score


def _collect_links(queries: list[str], is_data_request: bool) -> list[dict]:
    candidates = []
    seen_urls = set()

    with DDGS() as ddgs:
        for query in queries:
            try:
                results = ddgs.text(query, max_results=8) or []
            except Exception:
                continue

            for item in results:
                url = (item.get("href") or item.get("url") or "").strip()
                title = _clean_text(item.get("title", "Untitled"), limit=90)
                snippet = _clean_text(item.get("body", ""), limit=140)

                if not url or not url.startswith(("http://", "https://")):
                    continue
                if url in seen_urls:
                    continue

                seen_urls.add(url)
                candidates.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "host": _hostname(url),
                        "score": _score_result(title, snippet, is_data_request),
                    }
                )

    candidates.sort(key=lambda item: (item["score"], item["host"]), reverse=True)
    return candidates[:MAX_LINKS]


def _fallback_query_links(queries: list[str]) -> list[dict]:
    links = []
    for query in queries[:3]:
        encoded = query.replace(" ", "+")
        links.append(
            {
                "title": f"Web search: {query}",
                "url": f"https://duckduckgo.com/?q={encoded}",
                "snippet": "Direct search link generated when live results are unavailable.",
            }
        )
    return links


def _to_markdown(links: list[dict]) -> str:
    if not links:
        return ""

    lines = []
    for link in links:
        host = link.get("host") or _hostname(link.get("url", ""))
        title = link.get("title") or "External resource"
        text = f"{title} {link.get('snippet', '')}".lower()

        if "github" in host or "github" in text:
            reason = "Reference implementation or source examples you can inspect."
        elif "docs" in host or "documentation" in text or "official" in text:
            reason = "Official or documentation-style reference for implementation details."
        elif "tutorial" in text or "step by step" in text or "guide" in text:
            reason = "Practical walkthrough for building a similar feature."
        elif "dataset" in text or "benchmark" in text:
            reason = "Useful data reference for validating or training the project."
        else:
            reason = f"Relevant reference from {host}."

        lines.append(f"- [{link['title']}]({link['url']})\n  Source: {host} | {reason}")

    return "\n".join(lines)


def resource_agent(state):
    seed_text = (state.get("project_summary") or state.get("user_query") or "").strip()
    if not seed_text:
        state["external_resources"] = ""
        return state

    is_data_request = _is_data_or_model_request(seed_text)
    queries = _build_queries(state, is_data_request)
    links = _collect_links(queries, is_data_request)
    if not links and queries:
        links = _fallback_query_links(queries)

    state["external_resources"] = _to_markdown(links)
    return state
