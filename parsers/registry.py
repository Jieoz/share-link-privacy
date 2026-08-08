from __future__ import annotations

import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .base import ParseResult, host_of
from .platforms import ALL_PARSERS, UA

PARSERS = ALL_PARSERS

# Short hosts we will resolve via HTTP redirect (bounded).
SHORT_HOSTS = {
    "xhslink.com",
    "xhs.cn",
    "b23.tv",
    "bili2233.cn",
    "t.cn",
    "163cn.tv",
    "xima.tv",
    "dwz.cn",
    "url.cn",
    "u.wechat.com",
}

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


def extract_first_url(text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("http://") or text.startswith("https://"):
        # Trim common trailing punctuation from chat paste.
        return text.rstrip(")。.,，；;]")
    m = _URL_RE.search(text)
    if not m:
        return None
    return m.group(0).rstrip(")。.,，；;]")


def expand_short_url(url: str, timeout: float = 5.0, max_hops: int = 5) -> str:
    """Follow redirects for known short domains. Never posts body; GET only."""
    current = url
    for _ in range(max_hops):
        host = host_of(current)
        if host not in SHORT_HOSTS and not any(host.endswith("." + h) for h in SHORT_HOSTS):
            return current
        req = Request(
            current,
            method="GET",
            headers={"User-Agent": UA, "Accept": "text/html,*/*"},
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                final = resp.geturl() or current
                # Some short links return 200 HTML with a meta refresh / JS url.
                if final == current:
                    body = resp.read(8000).decode("utf-8", errors="replace")
                    m = re.search(
                        r'url\s*=\s*["\'](https?://[^"\']+)["\']',
                        body,
                        re.I,
                    ) or re.search(
                        r'href=["\'](https?://[^"\']+)["\']',
                        body,
                        re.I,
                    )
                    if m:
                        final = m.group(1)
                current = final
        except (URLError, HTTPError, TimeoutError, ValueError):
            return current
    return current


def supported_platforms() -> list[str]:
    return [p.name for p in PARSERS]


def parse_share_url(
    raw: str,
    *,
    expand: bool = True,
    enrich: bool = True,
) -> ParseResult:
    url = extract_first_url(raw)
    if not url:
        return ParseResult(ok=False, msg="请粘贴包含 http/https 的分享链接")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ParseResult(ok=False, msg="只支持 http/https 链接")

    working = expand_short_url(url) if expand else url

    matched_platform = False
    for parser in PARSERS:
        if not parser.matches(working) and not parser.matches(url):
            continue
        matched_platform = True
        result = parser.parse(working) or parser.parse(url)
        if result is None:
            continue
        if enrich:
            try:
                result = parser.enrich(result)
            except Exception:
                # Enrichment must never break core ID extraction.
                pass
        if not result.msg:
            result.msg = "已从分享链接解析出可能的账号标识。"
        return result

    if matched_platform:
        return ParseResult(
            ok=True,
            safe=True,
            msg="未发现分享人的账号",
        )

    return ParseResult(
        ok=True,
        safe=True,
        msg="不支持此应用的链接查询",
    )
