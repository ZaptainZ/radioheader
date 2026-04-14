#!/usr/bin/env python3
"""RadioHeader MCP Server.

Exposes the RadioHeader cross-project memory layer (topics, shortwave,
project registry, context digest) as MCP tools so any MCP-compatible
agent — Claude Desktop, Cursor, Windsurf, Gemini Code Assist, etc. —
can run the same "Search -> Apply -> Trace" behavior that Claude Code
and Codex CLI get through the native hooks.

Requires: pip install "mcp[cli]"
Run:      python3 radioheader-mcp-server.py

Configure your MCP client to start this script over stdio. The server
reads data from ~/.claude/radioheader/ (override via $RADIOHEADER_DIR).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    sys.stderr.write(
        "radioheader-mcp-server: the 'mcp' package is required.\n"
        "Install with: pip install \"mcp[cli]\"\n"
        f"Import error: {e}\n"
    )
    sys.exit(1)


# --- Paths ---------------------------------------------------------------

RADIOHEADER_DIR = Path(
    os.environ.get("RADIOHEADER_DIR", os.path.expanduser("~/.claude/radioheader"))
).resolve()
TOPICS_DIR = RADIOHEADER_DIR / "topics"
SHORTWAVE_DIR = RADIOHEADER_DIR / "shortwave"
COMMUNITY_POOL = RADIOHEADER_DIR / "community" / "pool"
PROJECT_REGISTRY_JSON = RADIOHEADER_DIR / "project-registry.json"
INDEX_MD = RADIOHEADER_DIR / "INDEX.md"
CONTEXT_DIGEST = RADIOHEADER_DIR / "context-digest.md"
USER_PROFILE = RADIOHEADER_DIR / "user-profile.md"
SEARCH_DB = RADIOHEADER_DIR / "search.db"


# --- Search backend import ----------------------------------------------
#
# fts-search.py lives next to this script after install.sh copies it. It
# exposes a `search()` function that returns a dict shaped for CLI use; we
# reuse it verbatim so the MCP surface and the CLI surface stay in sync.

_SEARCH_MODULE = None


def _load_search_module():
    global _SEARCH_MODULE
    if _SEARCH_MODULE is not None:
        return _SEARCH_MODULE

    # Prefer the fts-search.py that sits next to this script.
    candidates: list[Path] = []
    here = Path(__file__).resolve().parent
    candidates.append(here / "fts-search.py")
    # install.sh copies both scripts next to the CLI binary, so also look
    # alongside whichever radioheader executable we can find on PATH.
    for name in ("radioheader",):
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            if not directory:
                continue
            cli_path = Path(directory) / name
            if cli_path.exists():
                candidates.append(cli_path.parent / "fts-search.py")
                break

    for candidate in candidates:
        if candidate.is_file():
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "radioheader_fts_search", str(candidate)
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)  # type: ignore[union-attr]
                except Exception as exc:
                    sys.stderr.write(
                        f"radioheader-mcp-server: failed to load {candidate}: {exc}\n"
                    )
                    continue
                _SEARCH_MODULE = module
                return module

    return None


# --- Structured output shapes -------------------------------------------


class SearchHit(TypedDict, total=False):
    id: str
    source: str  # "shortwave" | "topic" | "community"
    domain: str
    tags: str
    title: str
    symptom: str
    fix: str
    file_path: str
    projects: str
    rank: float


class SearchResponse(TypedDict):
    query: str
    terms: list[str]
    expanded: list[str]
    count: int
    results: list[SearchHit]
    note: str


class ProjectSummary(TypedDict, total=False):
    name: str
    tech_stack: str
    path: str
    memory_path: str
    status: str
    domains: list[str]
    problems: list[str]
    pain_points: list[str]
    activity: float
    attention_weight: float
    last_active: str


class ShortwaveEntry(TypedDict, total=False):
    id: str
    path: str
    frontmatter: dict[str, Any]
    body: str


# --- Helpers ------------------------------------------------------------


def _read_project_registry() -> dict[str, Any]:
    if not PROJECT_REGISTRY_JSON.is_file():
        return {"version": 0, "projects": []}
    try:
        with PROJECT_REGISTRY_JSON.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"version": 0, "projects": []}


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_block, body = parts[1], parts[2]
    meta: dict[str, Any] = {}
    for raw in fm_block.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body.lstrip("\n")


def _safe_read_text(path: Path, max_chars: int = 16000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n... [truncated, file is {len(text)} chars]"
    return text


def _expand_user(path_str: str | None) -> str:
    if not path_str:
        return ""
    if path_str.startswith("~"):
        return os.path.expanduser(path_str)
    return path_str


def _str(value: Any) -> str:
    """Coerce any registry value to a non-null string."""
    if value is None:
        return ""
    return str(value)


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _project_to_summary(project: dict[str, Any]) -> ProjectSummary:
    return ProjectSummary(
        name=_str(project.get("name")),
        tech_stack=_str(project.get("tech_stack")),
        path=_expand_user(project.get("path")),
        memory_path=_expand_user(project.get("memory_path")),
        status=_str(project.get("status") or "active"),
        domains=list(project.get("domains") or []),
        problems=list(project.get("problems") or []),
        pain_points=list(project.get("pain_points") or []),
        activity=_safe_float(project.get("activity"), 0.0),
        attention_weight=_safe_float(project.get("attention_weight"), 1.0),
        last_active=_str(project.get("last_active")),
    )


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _resolve_shortwave(sw_id: str) -> Path | None:
    candidates: list[Path] = []
    name = sw_id.removesuffix(".md")
    name_sw = name if name.startswith("sw-") else f"sw-{name}"
    candidates.append(SHORTWAVE_DIR / f"{name_sw}.md")
    candidates.append(SHORTWAVE_DIR / f"{name}.md")
    for candidate in candidates:
        if candidate.is_file() and _is_under(candidate, SHORTWAVE_DIR):
            return candidate
    return None


# --- MCP server ---------------------------------------------------------


mcp = FastMCP(
    "RadioHeader",
    instructions=(
        "RadioHeader is a cross-project memory layer shared by Claude Code, "
        "Codex CLI, and any MCP-compatible agent. Before starting independent "
        "analysis, call `radioheader_search` with symptom keywords to see if a "
        "similar problem has already been solved. When an entry applies, cite "
        "it in your answer. When it doesn't, say so and proceed. Use "
        "`radioheader_trace_project` to find the source project's path and "
        "`radioheader_read_shortwave` / `radioheader_read_topic` to get the "
        "full text of an entry."
    ),
)


@mcp.tool()
def radioheader_search(
    query: str,
    field: str = "",
    expand: bool = True,
    limit: int = 20,
) -> SearchResponse:
    """Search RadioHeader topics, shortwave, and community entries.

    Uses BM25 ranking with automatic synonym expansion (e.g. "白屏" expands to
    "blank screen", "white screen"). Supports `|`-separated OR terms, the same
    syntax as the `radioheader search` CLI.

    Args:
        query: Search text. Use `|` between synonymous symptom keywords, e.g.
               "white screen|blank screen|slow launch".
        field: Optional single-field restriction — one of "tags", "domain",
               "id", "symptom", "fix", "context", "cause", "title". Leave
               empty to search all fields with column-weighted BM25.
        expand: Whether to expand query terms via the synonym table.
        limit: Maximum number of results (capped at 50).

    Returns:
        {query, terms, expanded, count, results[], note}
    """
    limit = max(1, min(limit, 50))
    module = _load_search_module()
    if module is None:
        return SearchResponse(
            query=query,
            terms=[],
            expanded=[],
            count=0,
            results=[],
            note=(
                "fts-search.py not found next to the MCP server. "
                "Run install.sh or place fts-search.py next to this script."
            ),
        )
    if not SEARCH_DB.is_file():
        return SearchResponse(
            query=query,
            terms=[],
            expanded=[],
            count=0,
            results=[],
            note=(
                "search.db is missing. Run `radioheader index --rebuild` "
                "to build the FTS5 index."
            ),
        )
    try:
        raw = module.search(
            query,
            field=field,
            expand=expand,
            limit=limit,
            attention=False,
        )
    except Exception as e:  # pragma: no cover - defensive
        return SearchResponse(
            query=query,
            terms=[],
            expanded=[],
            count=0,
            results=[],
            note=f"Search backend error: {e}",
        )

    note = ""
    if raw.get("expanded"):
        note = f"synonyms expanded: +{', '.join(raw['expanded'])}"
    elif raw.get("count", 0) == 0:
        note = (
            "No hits. Try different symptom keywords, "
            "or broaden with `|` separators."
        )

    return SearchResponse(
        query=raw.get("query", query),
        terms=list(raw.get("terms", [])),
        expanded=list(raw.get("expanded", [])),
        count=int(raw.get("count", 0)),
        results=list(raw.get("results", [])),
        note=note,
    )


@mcp.tool()
def radioheader_list_projects() -> list[ProjectSummary]:
    """List all projects registered in the RadioHeader project registry.

    Returns the same information the Agent needs to resolve a
    `[source:ProjectName]` tag to a real filesystem path, plus each
    project's known domains, problems, pain points, and recent activity.
    """
    registry = _read_project_registry()
    out: list[ProjectSummary] = []
    for project in registry.get("projects", []):
        if not isinstance(project, dict):
            continue
        out.append(_project_to_summary(project))
    return out


@mcp.tool()
def radioheader_trace_project(name: str) -> ProjectSummary:
    """Resolve a `[source:ProjectName]` tag to the source project record.

    When a topic or shortwave entry is tagged `[source:MyApp]`, call this
    to get MyApp's filesystem path, memory directory, tech stack, and
    known pain points. Use the returned path to read the project's
    `memory/` directory for deeper context.

    Args:
        name: Project name as it appears in `[source:ProjectName]` tags.
              Matching is case-insensitive and forgiving of whitespace.
    """
    target = name.strip().lower()
    registry = _read_project_registry()
    for project in registry.get("projects", []):
        if not isinstance(project, dict):
            continue
        candidate = (project.get("name") or "").strip().lower()
        if candidate == target or target in candidate.split("/"):
            return _project_to_summary(project)
    return ProjectSummary(
        name="",
        tech_stack="",
        path="",
        memory_path="",
        status="not-found",
        domains=[],
        problems=[],
        pain_points=[],
        activity=0.0,
        attention_weight=0.0,
        last_active="",
    )


@mcp.tool()
def radioheader_list_topics() -> list[dict[str, Any]]:
    """List topic files in ~/.claude/radioheader/topics/.

    Each entry returns the topic filename, its path, rough line count, and
    the first heading if one is present. Use this to browse available
    topic areas when search doesn't return anything useful.
    """
    out: list[dict[str, Any]] = []
    if not TOPICS_DIR.is_dir():
        return out
    for path in sorted(TOPICS_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        heading = ""
        for line in lines[:20]:
            stripped = line.strip()
            if stripped.startswith("# "):
                heading = stripped[2:].strip()
                break
        out.append(
            {
                "id": path.stem,
                "path": str(path),
                "line_count": len(lines),
                "heading": heading,
            }
        )
    return out


@mcp.tool()
def radioheader_read_topic(topic_id: str, max_chars: int = 16000) -> dict[str, Any]:
    """Read the full text of a topic file.

    Args:
        topic_id: Topic id or filename (with or without `.md`).
        max_chars: Truncate the file at this many characters.
    """
    name = topic_id if topic_id.endswith(".md") else f"{topic_id}.md"
    path = TOPICS_DIR / name
    if not path.is_file() or not _is_under(path, TOPICS_DIR):
        return {"id": topic_id, "path": "", "found": False, "content": ""}
    text = _safe_read_text(path, max_chars=max_chars)
    return {
        "id": path.stem,
        "path": str(path),
        "found": True,
        "content": text,
    }


@mcp.tool()
def radioheader_read_shortwave(
    shortwave_id: str, max_chars: int = 16000
) -> ShortwaveEntry:
    """Read a shortwave entry by id.

    Accepts any of:
        "sw-3d-blender-zup-usd-export"
        "3d-blender-zup-usd-export"
        "sw-3d-blender-zup-usd-export.md"
        "/full/path/to/shortwave.md"

    Returns parsed frontmatter plus the body text.
    """
    resolved = _resolve_shortwave(shortwave_id)
    if resolved is None:
        return ShortwaveEntry(
            id=shortwave_id,
            path="",
            frontmatter={},
            body="",
        )
    text = _safe_read_text(resolved, max_chars=max_chars)
    meta, body = _parse_frontmatter(text)
    return ShortwaveEntry(
        id=resolved.stem,
        path=str(resolved),
        frontmatter=meta,
        body=body,
    )


@mcp.tool()
def radioheader_context_digest(max_chars: int = 4000) -> dict[str, Any]:
    """Return the current RadioHeader context digest.

    The digest is produced by `radioheader consolidate` and summarizes the
    user's project landscape, working style, recent search patterns, and
    cross-project technology overlaps. Call this once at the start of a
    session to calibrate your understanding of who you're helping.
    """
    if not CONTEXT_DIGEST.is_file():
        return {
            "found": False,
            "path": str(CONTEXT_DIGEST),
            "content": "",
            "note": (
                "context-digest.md has not been generated yet. "
                "Run `radioheader consolidate` to build it."
            ),
        }
    return {
        "found": True,
        "path": str(CONTEXT_DIGEST),
        "content": _safe_read_text(CONTEXT_DIGEST, max_chars=max_chars),
        "note": "",
    }


@mcp.tool()
def radioheader_stats() -> dict[str, Any]:
    """Return a high-level status snapshot of the RadioHeader data layer.

    Useful as a lightweight health check — the MCP client can call this
    to confirm that topics, shortwave, the search index, and the project
    registry are all wired up before relying on the other tools.
    """

    def _count(directory: Path, pattern: str) -> int:
        if not directory.is_dir():
            return 0
        return sum(1 for _ in directory.glob(pattern))

    registry = _read_project_registry()
    return {
        "radioheader_dir": str(RADIOHEADER_DIR),
        "radioheader_dir_exists": RADIOHEADER_DIR.is_dir(),
        "topic_count": _count(TOPICS_DIR, "*.md"),
        "shortwave_count": _count(SHORTWAVE_DIR, "*.md"),
        "community_pool_count": _count(COMMUNITY_POOL, "*.md"),
        "project_count": len(registry.get("projects", [])),
        "search_index_ready": SEARCH_DB.is_file(),
        "context_digest_ready": CONTEXT_DIGEST.is_file(),
    }


def main() -> None:
    # FastMCP.run() defaults to stdio transport — exactly what MCP clients
    # like Claude Desktop, Cursor, and the MCP Inspector expect.
    mcp.run()


if __name__ == "__main__":
    main()
