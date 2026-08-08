# Share Link Privacy

从 App **分享链接**里解析可能泄露的分享者账号标识。  
灵感来自公开讨论的「分享链接身份追踪」问题（例如 [uid.ejfkdev.com](https://uid.ejfkdev.com/) 与作者掘金文章），本仓库是 **独立重写** 的开源实现，不包含对方源码。

## 它做什么 / 不做什么

| 做 | 不做 |
|---|---|
| 解析 URL / query / fragment 里的追踪参数 | 社工库、撞库、批量爬用户 |
| 拼公开主页链接 | 绕过登录墙或破解 token |
| 可选拉取**公开**资料补昵称头像 | 存储用户查询历史（默认无数据库） |
| 本地一键启动、可自托管 | 保证覆盖所有 App 的加密 share_token |

## 快速开始

需要 Python 3.10+（仅标准库）。

```bash
git clone https://github.com/Jieoz/share-link-privacy.git
cd share-link-privacy
python3 server.py --host 127.0.0.1 --port 8787
```

浏览器打开 <http://127.0.0.1:8787> 。

### API

```bash
curl -s http://127.0.0.1:8787/api/parse \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://music.163.com/song?id=1&userid=123456"}'
```

成功且发现账号时大致返回：

```json
{
  "ok": true,
  "platform": "网易云音乐",
  "id": "123456",
  "url": "https://y.music.163.com/m/user?id=123456",
  "msg": "..."
}
```

未发现或未支持：

```json
{"ok": true, "safe": true, "msg": "未发现分享人的账号"}
```

可选字段：`enrich`（默认 true，允许公开资料补全）、`expand`（默认 true，展开已知短链）。

## 已实现规则（可扩展）

小红书、网易云音乐、QQ 音乐、微博、知乎、酷安、B 站、Keep、喜马拉雅、雪球、知识星球、即刻、百度分享标识、汽水音乐等。

新增平台：在 `parsers/platforms.py` 增加 `PlatformParser` 子类，并加入 `ALL_PARSERS`。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 架构

```
浏览器 ──POST /api/parse──► server.py
                              │
                              ▼
                     parsers.registry
                     ├─ 抽 URL / 短链展开
                     ├─ 按域名匹配 PlatformParser
                     ├─ 抽 id → 拼 profile URL
                     └─ 可选 enrich（公开 API/HTML）
```

## 合规与伦理

- 本工具用于 **隐私教育与自我检测**。
- 用别人的链接去追踪、骚扰、人肉属违法或违反平台条款的风险由使用者自负。
- 厂商更稳妥的分享设计：服务端 `share_token`、或仅服务端可解的非对称加密，避免明文 / 可逆 uid。

## License

MIT
