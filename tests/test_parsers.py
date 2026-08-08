from __future__ import annotations

import unittest

from parsers import parse_share_url
from parsers.base import query_map
from parsers.registry import extract_first_url


class QueryMapTests(unittest.TestCase):
    def test_fragment_query(self):
        q = query_map("https://music.163.com/#/song?id=1&userid=42")
        self.assertEqual(q.get("userid"), "42")
        self.assertEqual(q.get("id"), "1")


class ExtractUrlTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(
            extract_first_url("https://example.com/a"),
            "https://example.com/a",
        )

    def test_embedded(self):
        self.assertEqual(
            extract_first_url("看看这个 https://music.163.com/song?id=1&userid=9 谢谢"),
            "https://music.163.com/song?id=1&userid=9",
        )

    def test_empty(self):
        self.assertIsNone(extract_first_url("没有链接"))


class ParserTests(unittest.TestCase):
    def test_unsupported(self):
        r = parse_share_url("https://example.com/?uid=1", expand=False, enrich=False)
        self.assertTrue(r.ok)
        self.assertTrue(r.safe)
        self.assertIn("不支持", r.msg)

    def test_not_url(self):
        r = parse_share_url("hello", expand=False, enrich=False)
        self.assertFalse(r.ok)

    def test_xhs_appuid(self):
        url = "https://www.xiaohongshu.com/discovery/item/abc?appuid=65559773000000001103ecc4"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertTrue(r.ok)
        self.assertFalse(r.safe)
        self.assertEqual(r.platform, "小红书")
        self.assertEqual(r.id, "65559773000000001103ecc4")
        self.assertIn("/user/profile/65559773000000001103ecc4", r.url or "")

    def test_xhs_no_tracker(self):
        url = "https://www.xiaohongshu.com/discovery/item/abc"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertTrue(r.ok)
        self.assertTrue(r.safe)
        self.assertIn("未发现", r.msg)

    def test_netease_userid(self):
        url = "https://music.163.com/song?id=186016&userid=123456"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertEqual(r.platform, "网易云音乐")
        self.assertEqual(r.id, "123456")
        self.assertIn("user?id=123456", r.url or "")

    def test_qq_hosteuin(self):
        url = "https://y.qq.com/n/ryqq/songDetail/001?hosteuin=oK4z"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertEqual(r.platform, "QQ音乐")
        self.assertEqual(r.id, "oK4z")
        self.assertIs(r.preview, False)

    def test_zhihu_utm_oi(self):
        url = "https://www.zhihu.com/question/1?utm_oi=123456"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertEqual(r.platform, "知乎")
        self.assertEqual(r.id, "123456")

    def test_coolapk_share_uid(self):
        url = "https://www.coolapk.com/feed/123?shareUid=999"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertEqual(r.platform, "酷安")
        self.assertEqual(r.id, "999")
        self.assertIn("/u/999", r.url or "")

    def test_weibo_bare_profile_is_safe(self):
        # Matches upstream: profile URL itself is not "share leakage".
        url = "https://m.weibo.cn/u/1764919567"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertTrue(r.safe)
        self.assertIsNone(r.id)

    def test_weibo_share_query_uid(self):
        url = "https://m.weibo.cn/status/ABC123?uid=1764919567"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertEqual(r.platform, "新浪微博")
        self.assertEqual(r.id, "1764919567")

    def test_bilibili_opaque_mid_not_decoded(self):
        url = "https://www.bilibili.com/video/BV1xx411c7mD?mid=2"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertEqual(r.platform, "哔哩哔哩")
        self.assertIsNone(r.id)
        self.assertIn("解密", r.msg)

    def test_bilibili_space_path(self):
        url = "https://space.bilibili.com/2"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertEqual(r.platform, "哔哩哔哩")
        self.assertEqual(r.id, "2")

    def test_keep_users_path_is_safe(self):
        url = "https://show.gotokeep.com/users/abc123"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertTrue(r.safe)

    def test_keep_share_uid_query(self):
        url = "https://show.gotokeep.com/entries/xyz?shareUid=abc123"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertEqual(r.platform, "Keep")
        self.assertEqual(r.id, "abc123")

    def test_xueqiu(self):
        url = "https://xueqiu.com/S/SH600000?share_uid=42"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertEqual(r.platform, "雪球")
        self.assertEqual(r.id, "42")

    def test_share_red_id_rejects_garbage(self):
        # Non hex-like shareRedId must not be treated as user id.
        url = "https://www.xiaohongshu.com/discovery/item/abc?shareRedId=not-a-uid!!"
        r = parse_share_url(url, expand=False, enrich=False)
        self.assertTrue(r.safe)


class ApiShapeTests(unittest.TestCase):
    def test_to_dict_omits_empties(self):
        r = parse_share_url(
            "https://music.163.com/song?id=1&userid=9",
            expand=False,
            enrich=False,
        )
        d = r.to_dict()
        self.assertIn("platform", d)
        self.assertIn("id", d)
        self.assertNotIn("extra", d)


if __name__ == "__main__":
    unittest.main()
