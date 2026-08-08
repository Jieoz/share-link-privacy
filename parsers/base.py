from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


@dataclass
class ParseResult:
    """Normalized parse outcome returned by /api/parse."""

    ok: bool = True
    safe: bool | None = None
    platform: str | None = None
    id: str | None = None
    name: str = ""
    avatar: str = ""
    url: str | None = None
    preview: bool | None = None
    msg: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Drop empty optional noise for a clean JSON response.
        if not data["extra"]:
            data.pop("extra")
        if data["safe"] is None:
            data.pop("safe")
        if data["preview"] is None:
            data.pop("preview")
        if not data["name"]:
            data.pop("name", None)
        if not data["avatar"]:
            data.pop("avatar", None)
        if not data["platform"]:
            data.pop("platform", None)
        if not data["id"]:
            data.pop("id", None)
        if not data["url"]:
            data.pop("url", None)
        if not data["msg"]:
            data.pop("msg", None)
        return data


def query_map(url: str) -> dict[str, str]:
    """Flatten query + fragment query into a single first-value map."""
    parsed = urlparse(url)
    out: dict[str, str] = {}
    for raw in (parsed.query, parsed.fragment):
        if not raw:
            continue
        # Fragments sometimes look like "/path?a=1" on SPA shares.
        q = raw
        if "?" in raw and "=" in raw.split("?", 1)[-1]:
            q = raw.split("?", 1)[-1]
        for key, values in parse_qs(q, keep_blank_values=False).items():
            if values and key not in out:
                out[key] = unquote(values[0])
    return out


def host_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def first_param(q: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = (q.get(name) or "").strip()
        if value:
            return value
    return None


def path_segments(url: str) -> list[str]:
    path = urlparse(url).path or ""
    return [p for p in path.split("/") if p]


class PlatformParser:
    """One platform's detection + profile URL construction."""

    name: str = "unknown"
    # Host suffixes this parser accepts (after stripping www.).
    hosts: tuple[str, ...] = ()

    def matches(self, url: str) -> bool:
        host = host_of(url)
        return any(host == h or host.endswith("." + h) for h in self.hosts)

    def parse(self, url: str) -> ParseResult | None:
        raise NotImplementedError

    def enrich(self, result: ParseResult) -> ParseResult:
        """Optional public-profile enrichment. Default: no network."""
        return result
