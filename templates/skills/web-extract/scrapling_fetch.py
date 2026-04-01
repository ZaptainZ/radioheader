#!/Users/zaptain/.claude/skills/web-extract/.venv/bin/python3
"""
网页正文提取脚本（Scrapling + html2text）

用法：python3 scrapling_fetch.py <url> [max_chars] [--stealth] [--cookie]
  --stealth  使用 StealthyFetcher（headless browser，用于反爬严格的站点）
  --cookie   使用本地浏览器 cookie（用于需要验证的站点如微信公众号，需用户确认）
默认 max_chars=30000

输出：JSON {"ok": bool, "content": str, "chars": int, "mode": str}
"""
import sys
import json


def _convert_to_markdown(page, max_chars: int) -> dict:
    """从 Scrapling page 对象提取正文并转 Markdown"""
    import html2text

    # 按优先级尝试正文选择器（微信 #js_content 优先）
    selectors = ["#js_content", ".rich_media_content", "article", "main", ".post-content", "[class*='body']", "[class*='content']", "#content"]
    element = None
    for sel in selectors:
        try:
            found = page.css(sel)
            if found:
                element = found[0]
                break
        except Exception:
            continue

    if element is None:
        try:
            body = page.css("body")
            if body:
                element = body[0]
        except Exception:
            return {"ok": False, "error": "无法定位页面正文"}

    if element is None:
        return {"ok": False, "error": "页面结构解析失败"}

    # html2text 转换
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0
    h.skip_internal_links = True
    h.ignore_emphasis = False

    try:
        html_content = element.html_content
        md = h.handle(html_content)
    except Exception:
        md = element.get_all_text(separator="\n")

    # 检查内容是否实质为空
    stripped = md.strip()
    if len(stripped) < 50:
        return {"ok": False, "error": f"内容过短({len(stripped)}字符)，可能被反爬拦截"}

    if len(md) > max_chars:
        md = md[:max_chars] + "\n\n[... 内容已截断，共 " + str(len(md)) + " 字符 ...]"

    return {"ok": True, "content": md, "chars": len(md)}


def _load_browser_cookies(domain: str) -> "http.cookiejar.CookieJar | None":
    """Try to load cookies from local browsers for a domain.

    Tries Chrome → Safari in order. Returns None if unavailable.
    """
    try:
        import browser_cookie3
    except ImportError:
        return None

    for loader in (browser_cookie3.chrome, browser_cookie3.safari):
        try:
            cj = loader(domain_name=domain)
            if any(True for _ in cj):
                return cj
        except Exception:
            continue
    return None


def extract_with_cookies(url: str, max_chars: int = 30000) -> dict:
    """Fetch using browser cookies (for sites requiring verification like WeChat)."""
    import urllib.parse
    domain = "." + urllib.parse.urlparse(url).hostname.split(".")[-2] + "." + urllib.parse.urlparse(url).hostname.split(".")[-1]

    cj = _load_browser_cookies(domain)
    if cj is None:
        return {"ok": False, "error": "无法读取浏览器 cookie（需安装 browser-cookie3 且浏览器中已访问过该站点）"}

    try:
        import urllib.request
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        opener.addheaders = [("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")]
        resp = opener.open(url, timeout=20)
        html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": f"Cookie 请求失败: {e}"}

    if len(html) < 200 or "appmsgcaptcha" in html or "环境异常" in html:
        return {"ok": False, "error": "Cookie 已过期或无效，浏览器中重新访问该站点后重试"}

    # Parse HTML with scrapling Selector for consistent _convert_to_markdown
    try:
        from scrapling import Selector
        page = Selector(html)
    except Exception:
        # Fallback: direct html2text
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0
        md = h.handle(html)
        if len(md) > max_chars:
            md = md[:max_chars] + "\n\n[... 内容已截断，共 " + str(len(md)) + " 字符 ...]"
        return {"ok": True, "content": md, "chars": len(md), "mode": "cookie-raw"}

    result = _convert_to_markdown(page, max_chars)
    if result["ok"]:
        result["mode"] = "cookie"
    return result


def extract_basic(url: str, max_chars: int = 30000) -> dict:
    """普通 Fetcher（快速，适合大部分站点）"""
    try:
        from scrapling import Fetcher
        import html2text  # noqa: F401
    except ImportError as e:
        return {"ok": False, "error": f"依赖未安装: {e}"}

    try:
        page = Fetcher.get(url, timeout=15)
    except Exception as e:
        return {"ok": False, "error": f"请求失败: {e}"}

    result = _convert_to_markdown(page, max_chars)
    if result["ok"]:
        result["mode"] = "fetcher"
    return result


def extract_stealth(url: str, max_chars: int = 30000) -> dict:
    """StealthyFetcher（headless browser，绕过反爬）"""
    try:
        from scrapling import StealthyFetcher
        import html2text  # noqa: F401
    except ImportError as e:
        return {"ok": False, "error": f"依赖未安装: {e}"}

    try:
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            wait_selector="#js_content, .rich_media_content, article, main",
            timeout=30000,
        )
    except Exception as e:
        return {"ok": False, "error": f"Stealth 请求失败: {e}"}

    result = _convert_to_markdown(page, max_chars)
    if result["ok"]:
        result["mode"] = "stealth"
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "用法: scrapling_fetch.py <url> [max_chars] [--stealth] [--cookie]"}))
        sys.exit(1)

    url = sys.argv[1]
    use_stealth = "--stealth" in sys.argv
    use_cookie = "--cookie" in sys.argv
    args_without_flags = [a for a in sys.argv[2:] if not a.startswith("--")]
    max_chars = int(args_without_flags[0]) if args_without_flags else 30000

    if use_cookie:
        # 显式 cookie 模式（需用户确认后由 SKILL.md 调用）
        result = extract_with_cookies(url, max_chars)
    elif use_stealth:
        result = extract_stealth(url, max_chars)
    else:
        # 默认：basic → stealth（内容过短时自动降级）
        result = extract_basic(url, max_chars)
        if not result["ok"] and "内容过短" in result.get("error", ""):
            result = extract_stealth(url, max_chars)

    print(json.dumps(result, ensure_ascii=False))
