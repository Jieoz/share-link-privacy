#!/usr/bin/env python3
"""Compare local /api/parse against uid.ejfkdev.com/api/parse on the same URLs.

Network required. SSL on upstream may be broken — we use ssl unverified.
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parsers import parse_share_url  # noqa: E402

UPSTREAM = "https://uid.ejfkdev.com/api/parse"
CTX = ssl._create_unverified_context()
UA = "ShareLinkPrivacyCompare/1.0"


def post_upstream(url: str, timeout: float = 12.0) -> dict:
    # Live upstream accepts top-level {"url": ...}. Nested {"data":{"url"}} returns
    # a generic error (verified 2026-08-08).
    body = json.dumps({"url": url}).encode()
    req = urllib.request.Request(
        UPSTREAM,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Origin": "https://uid.ejfkdev.com",
            "Referer": "https://uid.ejfkdev.com/",
            "Accept": "application/json, text/plain, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"ok": False, "msg": f"HTTP {e.code}: {raw[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "msg": f"{type(e).__name__}: {e}"}


def post_local(url: str, base: str = "http://127.0.0.1:8787", enrich: bool = True) -> dict:
    body = json.dumps({"url": url, "enrich": enrich}).encode()
    req = urllib.request.Request(
        f"{base}/api/parse",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


# Fixtures: mix of synthetic tracker-bearing URLs + edge cases.
CASES = [
    (
        "xhs_appuid",
        "https://www.xiaohongshu.com/discovery/item/64f000000000000000000001"
        "?appuid=65559773000000001103ecc4&share_id=abc",
    ),
    (
        "xhs_no_tracker",
        "https://www.xiaohongshu.com/discovery/item/64f000000000000000000001",
    ),
    (
        "netease_userid",
        "https://music.163.com/song?id=186016&userid=32953014",
    ),
    (
        "qq_hosteuin",
        "https://i.y.qq.com/v8/playsong.html?songid=1&hosteuin=oK4z7iCk7iCk",
    ),
    (
        "zhihu_utm_oi",
        "https://www.zhihu.com/question/19550225?utm_oi=1234567890",
    ),
    (
        "coolapk_shareUid",
        "https://www.coolapk.com/feed/123456?shareUid=10086",
    ),
    (
        "weibo_bare_profile",
        "https://m.weibo.cn/u/1764919567",
    ),
    (
        # Synthetic ?uid= on status is NOT currently decoded by upstream (2026-08-08).
        "weibo_status_uid_extension",
        "https://m.weibo.cn/status/ABC123?uid=1764919567",
    ),
    (
        "bilibili_opaque_mid",
        "https://www.bilibili.com/video/BV1xx411c7mD?mid=2",
    ),
    (
        "xueqiu_share_uid",
        "https://xueqiu.com/S/SH600000?share_uid=12345",
    ),
    (
        "keep_users_path",
        "https://show.gotokeep.com/users/5a1b2c3d4e5f",
    ),
    (
        "keep_share_uid_extension",
        "https://show.gotokeep.com/entries/xyz?shareUid=5a1b2c3d4e5f",
    ),
    (
        "unsupported",
        "https://example.com/foo?uid=1",
    ),
    (
        "emptyish",
        "not a url",
    ),
]


def summarize(d: dict) -> str:
    if not isinstance(d, dict):
        return repr(d)
    keys = ["ok", "safe", "platform", "id", "name", "url", "preview", "msg"]
    bits = []
    for k in keys:
        if k in d and d[k] not in (None, ""):
            v = d[k]
            if isinstance(v, str) and len(v) > 80:
                v = v[:77] + "..."
            bits.append(f"{k}={v!r}")
    return " | ".join(bits) if bits else json.dumps(d, ensure_ascii=False)[:120]


def is_hit(d: dict) -> bool:
    return bool(d.get("ok") and d.get("id") and d.get("safe") is not True)


def same_core(a: dict, b: dict) -> tuple[bool, str]:
    """Compare identity-bearing fields; tolerate msg/name/avatar differences."""
    if a.get("ok") is False and b.get("ok") is False:
        return True, "both_error"

    def is_platform_note(d: dict) -> bool:
        return bool(
            d.get("ok") and d.get("platform") and not d.get("id") and d.get("safe") is not True
        )

    def is_safe(d: dict) -> bool:
        return bool(
            d.get("ok")
            and (d.get("safe") is True or (not d.get("id") and not d.get("platform")))
        )

    a_hit, b_hit = is_hit(a), is_hit(b)
    if a_hit or b_hit:
        if a_hit != b_hit:
            return False, f"hit_mismatch local_hit={a_hit} up_hit={b_hit}"
        if str(a.get("id")) != str(b.get("id")):
            return False, f"id {a.get('id')!r} vs {b.get('id')!r}"
        if not a.get("platform") or not b.get("platform"):
            return False, "missing platform"
        return True, "hit_id_match"

    if is_platform_note(a) or is_platform_note(b):
        if is_platform_note(a) and is_platform_note(b) and a.get("platform") == b.get("platform"):
            return True, "platform_note_match"
        return False, f"platform_note_mismatch local={summarize(a)} up={summarize(b)}"

    if is_safe(a) and is_safe(b):
        return True, "both_safe_or_no_id"

    return False, f"shape local={summarize(a)} up={summarize(b)}"


def main() -> int:
    print("== direct library (no network enrich) ==")
    for name, url in CASES:
        r = parse_share_url(url, expand=False, enrich=False)
        print(f"  [{name}] {summarize(r.to_dict())}")

    print("\n== local HTTP vs upstream HTTP ==")
    rows = []
    for name, url in CASES:
        try:
            local = post_local(url, enrich=False)
        except Exception as e:  # noqa: BLE001
            local = {"ok": False, "msg": f"local_fail {e}"}
        up = post_upstream(url)
        ok, reason = same_core(local, up)
        # Known local-only extensions (upstream returns safe on these synthetics).
        if (not ok) and name.endswith("_extension") and up.get("safe") and is_hit(local):
            ok, reason = True, "local_extension_ok_upstream_safe"
        rows.append((name, ok, reason, local, up, url))
        mark = "OK " if ok else "DIFF"
        print(f"\n[{mark}] {name}")
        print(f"  url: {url[:100]}")
        print(f"  local:    {summarize(local)}")
        print(f"  upstream: {summarize(up)}")
        print(f"  judge:    {reason}")

    n_ok = sum(1 for r in rows if r[1])
    n = len(rows)
    print(f"\n== summary: {n_ok}/{n} core-equivalent ==")
    diffs = [r for r in rows if not r[1]]
    if diffs:
        print("DIFF cases:")
        for name, _, reason, _local, _up, _url in diffs:
            print(f"  - {name}: {reason}")
    return 0 if n_ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
