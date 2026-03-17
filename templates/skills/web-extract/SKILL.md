---
name: web-extract
description: Extract clean article text from any URL (Markdown format). Three-tier fallback strategy: Jina Reader → Scrapling + html2text → web_fetch. Trigger keywords: "fetch article", "extract web", "read URL", "web extract", "grab article", "read this page", "extract content". Auto-triggers when user provides a URL and asks to read/extract its content.
---

# Web Article Extraction — Three-Tier Fallback Strategy

## Overview

Extract clean Markdown text from any URL, automatically selecting the best approach. Unified maxChars=30000.

## Input

User-provided URL is in `$ARGUMENTS`. If no URL provided, ask the user.

## Execution Strategy

### Domain Quick Routes (check first)

| Domain Pattern | Direct to | Reason |
|----------------|-----------|--------|
| `mp.weixin.qq.com` | **Scrapling** | Jina gets 403, don't waste quota |
| `github.com` | **web_fetch** | Static page, Jina unnecessary |
| `raw.githubusercontent.com` | **web_fetch** | Raw file |
| `docs.*` / `*.readthedocs.io` | **web_fetch** | Tech docs, static |

### Non-routed → Three-Tier Fallback

**Tier 1: Jina Reader (preferred)**

```
Use WebFetch tool to access: https://r.jina.ai/{original_URL}
Set maxChars=30000
```

Jina auto-renders, extracts main content, removes noise. Returns clean Markdown. ~1.4s.
- 200 free requests/day
- If returns empty, 403, or obviously incomplete → fall back to Tier 2

**Tier 2: Scrapling + html2text (fallback)**

```bash
~/.claude/skills/web-extract/.venv/bin/python3 ~/.claude/skills/web-extract/scrapling_fetch.py "<URL>" 30000
```

Dependencies are installed in the skill's own venv.

Features:
- Unlimited, no API Key needed
- Bypasses Cloudflare, WeChat, and other anti-scraping measures
- With html2text, output quality matches Jina
- If script errors → fall back to Tier 3

**Tier 3: web_fetch direct (last resort)**

```
Use WebFetch tool to directly access the original URL
Set maxChars=30000
```

Note:
- Returns full-page HTML→Markdown, lots of noise
- Anti-scraping platforms will fail outright
- Only suitable for static pages

### Tier 4 (extreme cases): Browser

If all three tiers fail, inform user they can:
- Open the page in a browser manually and paste content
- Consider setting up a browser tool with login state

## Output Format

After successful extraction, show the user:

1. **Approach used**: Which tier (Jina / Scrapling / web_fetch)
2. **Article content**: Clean Markdown
3. **Character count**: Actual extracted characters
4. If fallback occurred, briefly explain why

## Dependencies

Scrapling and html2text are installed in the skill's own venv: `~/.claude/skills/web-extract/.venv/`

To reinstall:
```bash
~/.claude/skills/web-extract/.venv/bin/pip install scrapling html2text browserforge
```

Jina and web_fetch tiers need no extra dependencies.

## Notes

- Don't call multiple tiers simultaneously — fall back in order
- WeChat Official Account articles go straight to Scrapling, don't waste Jina quota
- maxChars unified at 30000: save tokens while preserving complete article
- Extracted content is for AI consumption — preserving links and image URLs is valuable
