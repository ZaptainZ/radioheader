---
name: web-extract
description: 从任意 URL 提取干净正文（Markdown 格式）。三层降级策略：Jina Reader → Scrapling + html2text → web_fetch。触发关键词：「抓取网页」「提取正文」「读取文章」「网页内容」「fetch article」「extract web」「读取 URL」「抓文章」「web extract」「网页提取」。当用户给出一个 URL 并要求获取/阅读/提取其内容时自动触发。
---

# 网页正文提取 — 三层降级 + Cookie 辅助

## 概述

从任意 URL 提取干净的 Markdown 正文，自动选择最优方案。统一 maxChars=30000。

## 输入

用户提供的 URL 在 `$ARGUMENTS` 中。如果没有提供 URL，询问用户。

## 执行策略

### 域名快捷路由（优先判断）

| 域名模式 | 直接走 | 原因 |
|----------|--------|------|
| `mp.weixin.qq.com` | **Scrapling** | Jina 403，不浪费配额 |
| `github.com` | **web_fetch** | 静态页，无需 Jina |
| `raw.githubusercontent.com` | **web_fetch** | 原始文件 |
| `docs.*` / `*.readthedocs.io` | **web_fetch** | 技术文档，静态 |

### 非快捷路由 → 三层降级

**第一层：Jina Reader（优先）**

```
使用 WebFetch 工具访问: https://r.jina.ai/{原始URL}
设置 maxChars=30000
```

Jina 自动渲染、抽取正文、去噪，返回干净 Markdown。速度约 1.4 秒。
- 每天免费 200 次
- 如果返回内容为空、403、或明显不完整 → 降级到第二层

**第二层：Scrapling + html2text（降级）**

```bash
~/.claude/skills/web-extract/.venv/bin/python3 ~/.claude/skills/web-extract/scrapling_fetch.py "<URL>" 30000
```

依赖已安装在 skill 自带的 venv 中，无需额外操作。

特点：
- 无限制，无需 API Key
- 配合 html2text 输出与 Jina 同等质量的 Markdown
- 如果脚本报错（依赖未装等）→ 降级到第三层

**第三层：web_fetch 直接抓（兜底）**

```
使用 WebFetch 工具直接访问原始 URL
设置 maxChars=30000
```

注意：
- 返回全页 HTML 转 Markdown，噪音多
- 有反爬的平台会直接失败
- 仅适合静态页面

### 验证拦截检测 + Cookie 辅助（第四层）

**当以上三层返回的内容包含以下特征时，判定为被验证拦截：**
- 内容含"环境异常"、"完成验证"、"appmsgcaptcha"等字样
- 返回内容为空或明显是验证页（而非正文）
- Scrapling 报超时且域名为 `mp.weixin.qq.com` 等已知需验证站点

**检测到拦截后，必须告知用户并请求确认：**

> 该网站需要人机验证，常规提取方式无法获取正文。
> 我可以尝试使用你本地浏览器（Chrome/Safari）中已有的 cookie 来绕过验证。
> 这会读取你浏览器中该站点的 cookie（仅用于本次请求，不会存储或外传）。
>
> 是否允许使用浏览器 cookie 提取？

**用户确认后**，使用 `--cookie` 标志调用：

```bash
~/.claude/skills/web-extract/.venv/bin/python3 ~/.claude/skills/web-extract/scrapling_fetch.py "<URL>" 30000 --cookie
```

**用户拒绝时**，告知替代方案：
- 在浏览器中手动打开文章，复制正文粘贴到对话中
- 或将文章链接转发给自己后用其他阅读器打开

### 已知需要 cookie 的站点

| 域名 | 原因 |
|------|------|
| `mp.weixin.qq.com` | 微信公众号文章，2026 年起要求 PoC 验证码 |

遇到新的需验证站点时，同样走「检测 → 提示 → 确认 → cookie」流程。

## 输出格式

提取成功后，向用户展示：

1. **使用的方案**：告知用了哪一层（Jina / Scrapling / web_fetch / Cookie）
2. **正文内容**：干净的 Markdown
3. **字符数**：实际提取的字符数
4. 如果发生降级或使用了 cookie，简要说明原因

## 依赖

Scrapling、html2text、browser-cookie3 已安装在 skill 自带的 venv 中：`~/.claude/skills/web-extract/.venv/`

如需重装：
```bash
~/.claude/skills/web-extract/.venv/bin/pip install scrapling html2text browser-cookie3
```

Jina 和 web_fetch 层无需额外依赖。

## 注意事项

- 不要对同一 URL 同时调用多层，按顺序降级
- 微信公众号文章直接走 Scrapling（跳过 Jina），不浪费 Jina 配额
- **cookie 模式必须经用户明确同意后才能使用**，不得自动调用
- cookie 仅用于本次 HTTP 请求，不做任何持久化或外传
- maxChars 统一 30000：省 token 同时保留完整正文
- 提取的内容用于 AI 消化，保留链接和图片 URL 有价值
