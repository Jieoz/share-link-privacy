from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import ParseResult, PlatformParser, first_param, host_of, path_segments, query_map

UA = (
    "Mozilla/5.0 (compatible; ShareLinkPrivacy/1.0; +https://github.com/Jieoz/share-link-privacy)"
)


def _http_get_json(url: str, timeout: float = 5.0) -> dict | None:
    req = Request(url, headers={"User-Agent": UA, "Referer": "https://music.163.com/"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200_000)
        return json.loads(raw.decode("utf-8", errors="replace"))
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


def _http_get_text(url: str, timeout: float = 5.0) -> str | None:
    req = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read(300_000).decode("utf-8", errors="replace")
    except (URLError, HTTPError, TimeoutError, ValueError):
        return None


class XiaohongshuParser(PlatformParser):
    name = "小红书"
    hosts = ("xiaohongshu.com", "xhslink.com", "xhs.cn")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "appuid", "share_user_id", "userId", "user_id", "uid")
        # shareRedId is often an opaque tracking token; only accept hex-like user ids.
        if not uid:
            candidate = first_param(q, "shareRedId", "share_id")
            if candidate and re.fullmatch(r"[0-9a-fA-F]{16,32}", candidate):
                uid = candidate
        if not uid:
            segs = path_segments(url)
            if "user" in segs and "profile" in segs:
                try:
                    uid = segs[segs.index("profile") + 1]
                except (ValueError, IndexError):
                    uid = None
        if not uid:
            return None
        profile = f"https://www.xiaohongshu.com/user/profile/{uid}"
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=uid,
            url=profile,
            msg="从分享链接参数解析出用户 id；头像昵称需打开主页查看。",
        )


class NeteaseMusicParser(PlatformParser):
    name = "网易云音乐"
    hosts = ("music.163.com", "y.music.163.com", "163cn.tv", "163.com")

    def matches(self, url: str) -> bool:
        host = host_of(url)
        if host in {"163cn.tv"}:
            return True
        if host.endswith("music.163.com") or host == "music.163.com":
            return True
        # Avoid claiming all of 163.com.
        return "music.163.com" in url

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "userid", "userId", "uid", "share_id")
        if not uid:
            # /user/home?id= / user?id=
            m = re.search(r"[?&#]id=(\d+)", url)
            if m and ("user" in url or "home" in url):
                uid = m.group(1)
        if not uid or not uid.isdigit():
            return None
        profile = f"https://y.music.163.com/m/user?id={uid}"
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=uid,
            url=profile,
            msg="如果是用电脑查询，复制主页链接手动打开～",
        )

    def enrich(self, result: ParseResult) -> ParseResult:
        if not result.id:
            return result
        data = _http_get_json(f"https://music.163.com/api/v1/user/detail/{result.id}")
        if not data:
            return result
        profile = (data.get("profile") or {}) if isinstance(data, dict) else {}
        name = (profile.get("nickname") or "").strip()
        avatar = (profile.get("avatarUrl") or "").strip()
        if name:
            result.name = name
        if avatar:
            result.avatar = avatar
        return result


class QQMusicParser(PlatformParser):
    name = "QQ音乐"
    hosts = ("y.qq.com", "i.y.qq.com", "qq.com")

    def matches(self, url: str) -> bool:
        host = host_of(url)
        return host in {"y.qq.com", "i.y.qq.com"} or host.endswith(".y.qq.com")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uin = first_param(q, "hosteuin", "encrypt_uin", "share_uin", "uin")
        if not uin:
            return None
        profile = (
            "https://y.qq.com/n3/other/pages/share/profile_v2/index.html"
            f"?encrypt_uin={uin}"
        )
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=uin,
            url=profile,
            preview=False,
            msg="需要登录后查看，复制上面的链接在浏览器打开。",
        )


class WeiboParser(PlatformParser):
    name = "新浪微博"
    hosts = ("weibo.com", "weibo.cn", "m.weibo.cn", "t.cn")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "uid", "luicode")  # luicode alone is not uid; filtered below
        # Prefer explicit uid query.
        uid = first_param(q, "uid")
        if not uid:
            segs = path_segments(url)
            # /u/123456 or /123456/profile
            for i, seg in enumerate(segs):
                if seg in {"u", "profile"} and i + 1 < len(segs) and segs[i + 1].isdigit():
                    uid = segs[i + 1]
                    break
                if seg.isdigit() and len(seg) >= 5 and i > 0 and segs[i - 1] in {"u", "n"}:
                    uid = seg
                    break
            # path /1720337310/AbCdEf style status with numeric author? skip — too ambiguous
        if not uid:
            m = re.search(r"(?:weibo\.(?:com|cn))/u/(\d+)", url)
            if m:
                uid = m.group(1)
        if not uid or not str(uid).isdigit():
            return None
        profile = f"https://m.weibo.cn/u/{uid}"
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(uid),
            url=profile,
            msg="已从链接中解析出微博 uid。",
        )


class ZhihuParser(PlatformParser):
    name = "知乎"
    hosts = ("zhihu.com", "www.zhihu.com")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        oid = first_param(q, "utm_oi", "share_id")
        if not oid:
            segs = path_segments(url)
            if "people" in segs:
                try:
                    oid = segs[segs.index("people") + 1]
                except (ValueError, IndexError):
                    oid = None
        if not oid:
            return None
        # utm_oi is not always a public people url_token; keep consult fallback like upstream idea.
        if str(oid).isdigit():
            profile = f"https://www.zhihu.com/consult/people/{oid}"
            msg = "复制链接到浏览器打开；utm_oi 数字 id 不一定对应公开主页。"
            preview = False
        else:
            profile = f"https://www.zhihu.com/people/{oid}"
            msg = "已解析知乎用户标识。"
            preview = True
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(oid),
            url=profile,
            preview=preview,
            msg=msg,
        )


class CoolapkParser(PlatformParser):
    name = "酷安"
    hosts = ("coolapk.com",)

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "shareUid", "shareuid", "uid")
        if not uid:
            segs = path_segments(url)
            if "u" in segs:
                try:
                    uid = segs[segs.index("u") + 1]
                except (ValueError, IndexError):
                    uid = None
        if not uid:
            return None
        profile = f"https://www.coolapk.com/u/{uid}"
        result = ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(uid),
            url=profile,
            preview=False,
            msg="复制上面的链接在浏览器打开，需要安装酷安 app。",
        )
        return result

    def enrich(self, result: ParseResult) -> ParseResult:
        if not result.url:
            return result
        html = _http_get_text(result.url)
        if not html:
            return result
        m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if m:
            title = m.group(1).strip()
            # Typical: "昵称的动态 - 酷安"
            name = re.split(r"的动态| - |\|", title)[0].strip()
            if name and name not in {"酷安", "Coolapk"}:
                result.name = name
        return result


class BilibiliParser(PlatformParser):
    name = "哔哩哔哩"
    hosts = ("bilibili.com", "b23.tv", "bili2233.cn")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        mid = first_param(q, "mid", "share_mid", "uid")
        if not mid:
            segs = path_segments(url)
            if "space" in segs:
                try:
                    mid = segs[segs.index("space") + 1]
                except (ValueError, IndexError):
                    mid = None
        if not mid or not str(mid).isdigit():
            return None
        profile = f"https://space.bilibili.com/{mid}"
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(mid),
            url=profile,
            msg="已从链接解析出 mid。",
        )


class KeepParser(PlatformParser):
    name = "Keep"
    hosts = ("gotokeep.com", "keep.com")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "shareUid", "userId", "userid", "uid")
        if not uid:
            segs = path_segments(url)
            if "users" in segs:
                try:
                    uid = segs[segs.index("users") + 1]
                except (ValueError, IndexError):
                    uid = None
        if not uid:
            return None
        profile = f"https://show.gotokeep.com/users/{uid}"
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(uid),
            url=profile,
            msg="已解析 Keep 用户标识。",
        )


class XimalayaParser(PlatformParser):
    name = "喜马拉雅"
    hosts = ("ximalaya.com", "xima.tv")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "shareUid", "uid", "userId")
        if not uid:
            segs = path_segments(url)
            for key in ("zhubo", "user"):
                if key in segs:
                    try:
                        uid = segs[segs.index(key) + 1]
                        break
                    except (ValueError, IndexError):
                        pass
        if not uid:
            return None
        profile = f"https://www.ximalaya.com/zhubo/{uid}"
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(uid),
            url=profile,
            msg="已解析喜马拉雅主播/用户 id。",
        )


class XueqiuParser(PlatformParser):
    name = "雪球"
    hosts = ("xueqiu.com",)

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "share_uid", "shareUid", "uid")
        if not uid:
            segs = path_segments(url)
            if "u" in segs:
                try:
                    uid = segs[segs.index("u") + 1]
                except (ValueError, IndexError):
                    uid = None
        if not uid:
            return None
        profile = f"https://xueqiu.com/u/{uid}"
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(uid),
            url=profile,
            msg="已解析雪球用户 id。",
        )


class ZsxqParser(PlatformParser):
    name = "知识星球"
    hosts = ("zsxq.com", "t.zsxq.com", "wx.zsxq.com")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "inviter_id", "share_from_user_id", "user_id", "uid")
        if not uid:
            return None
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(uid),
            url=None,
            preview=False,
            msg="解析到邀请/分享者 id；知识星球主页通常需登录圈子后查看。",
        )


class JikeParser(PlatformParser):
    name = "即刻"
    hosts = ("okjike.com", "m.okjike.com", "web.okjike.com")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "username", "userId", "uid", "share_user_id")
        if not uid:
            segs = path_segments(url)
            if "users" in segs:
                try:
                    uid = segs[segs.index("users") + 1]
                except (ValueError, IndexError):
                    uid = None
        if not uid:
            return None
        profile = f"https://web.okjike.com/u/{uid}"
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(uid),
            url=profile,
            msg="已解析即刻用户标识。",
        )


class BaiduParser(PlatformParser):
    name = "百度"
    hosts = ("baidu.com", "mbd.baidu.com", "pan.baidu.com")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "share_uk", "uk", "uid", "third")
        if not uid:
            return None
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(uid),
            url=None,
            preview=False,
            msg="解析到百度分享者标识（uk 等）；是否可打开主页取决于业务线。",
        )


class QishuiParser(PlatformParser):
    name = "汽水音乐"
    hosts = ("qishui.douyin.com", "music.douyin.com", "qishui.com")

    def parse(self, url: str) -> ParseResult | None:
        q = query_map(url)
        uid = first_param(q, "share_uid", "shareUid", "uid", "user_id")
        if not uid:
            return None
        return ParseResult(
            ok=True,
            safe=False,
            platform=self.name,
            id=str(uid),
            url=None,
            preview=False,
            msg="解析到汽水/抖音音乐分享者 id；网页主页能力因版本而异。",
        )


ALL_PARSERS: list[PlatformParser] = [
    XiaohongshuParser(),
    NeteaseMusicParser(),
    QQMusicParser(),
    WeiboParser(),
    ZhihuParser(),
    CoolapkParser(),
    BilibiliParser(),
    KeepParser(),
    XimalayaParser(),
    XueqiuParser(),
    ZsxqParser(),
    JikeParser(),
    BaiduParser(),
    QishuiParser(),
]
