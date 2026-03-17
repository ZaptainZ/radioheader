#!/usr/bin/env python3
"""
Web article extraction script (Scrapling + html2text)

Usage: python3 scrapling_fetch.py <url> [max_chars] [--stealth]
  --stealth  Use StealthyFetcher (headless browser, for strict anti-scraping sites)
Default max_chars=30000

Output: JSON {"ok": bool, "content": str, "chars": int, "mode": str}

Part of RadioHeader's web-extract skill.
After installation, the shebang is updated to point to the skill's venv Python.
"""
import sys
import json


def _convert_to_markdown(page, max_chars: int) -> dict:
    """Extract main content from Scrapling page object, convert to Markdown"""
    import html2text

    # Selector priority: WeChat #js_content first, then standard selectors
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
            return {"ok": False, "error": "Cannot locate page content"}

    if element is None:
        return {"ok": False, "error": "Page structure parsing failed"}

    # html2text conversion
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

    # Check if content is essentially empty
    stripped = md.strip()
    if len(stripped) < 50:
        return {"ok": False, "error": f"Content too short ({len(stripped)} chars), likely blocked by anti-scraping"}

    if len(md) > max_chars:
        md = md[:max_chars] + "\n\n[... truncated, total " + str(len(md)) + " chars ...]"

    return {"ok": True, "content": md, "chars": len(md)}


def extract_basic(url: str, max_chars: int = 30000) -> dict:
    """Basic Fetcher (fast, works for most sites)"""
    try:
        from scrapling import Fetcher
        import html2text  # noqa: F401
    except ImportError as e:
        return {"ok": False, "error": f"Dependencies not installed: {e}"}

    try:
        page = Fetcher.get(url, timeout=15)
    except Exception as e:
        return {"ok": False, "error": f"Request failed: {e}"}

    result = _convert_to_markdown(page, max_chars)
    if result["ok"]:
        result["mode"] = "fetcher"
    return result


def extract_stealth(url: str, max_chars: int = 30000) -> dict:
    """StealthyFetcher (headless browser, bypasses anti-scraping)"""
    try:
        from scrapling import StealthyFetcher
        import html2text  # noqa: F401
    except ImportError as e:
        return {"ok": False, "error": f"Dependencies not installed: {e}"}

    try:
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            wait_selector="#js_content, .rich_media_content, article, main",
            timeout=30000,
        )
    except Exception as e:
        return {"ok": False, "error": f"Stealth request failed: {e}"}

    result = _convert_to_markdown(page, max_chars)
    if result["ok"]:
        result["mode"] = "stealth"
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "Usage: scrapling_fetch.py <url> [max_chars] [--stealth]"}))
        sys.exit(1)

    url = sys.argv[1]
    use_stealth = "--stealth" in sys.argv
    args_without_flags = [a for a in sys.argv[2:] if not a.startswith("--")]
    max_chars = int(args_without_flags[0]) if args_without_flags else 30000

    if use_stealth:
        result = extract_stealth(url, max_chars)
    else:
        # Auto-fallback: try basic first, if content too short try stealth
        result = extract_basic(url, max_chars)
        if not result["ok"] and "too short" in result.get("error", ""):
            result = extract_stealth(url, max_chars)

    print(json.dumps(result, ensure_ascii=False))
