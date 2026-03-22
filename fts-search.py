#!/usr/bin/env python3
"""
RadioHeader FTS5 Search

Searches the FTS5 index with BM25 ranking and synonym expansion.

Usage:
  python3 fts-search.py "keyword"
  python3 fts-search.py --field=tags "keyword"
  python3 fts-search.py --expand "白屏"       # auto-expand to synonyms

Output: JSON array of results for CLI consumption.
"""

import json
import os
import re
import sys
import sqlite3
from datetime import datetime, date
from pathlib import Path


def get_db_path():
    rdir = os.environ.get("RADIOHEADER_DIR", os.path.expanduser("~/.claude/radioheader"))
    return os.path.join(rdir, "search.db")


def expand_synonyms(conn: sqlite3.Connection, terms: list[str]) -> list[str]:
    """Expand search terms with synonyms from the database."""
    expanded = set(terms)
    for term in terms:
        rows = conn.execute(
            "SELECT synonym FROM synonyms WHERE term = ?", (term.lower(),)
        ).fetchall()
        for (syn,) in rows:
            expanded.add(syn)
    return sorted(expanded)


def fts5_escape(term: str) -> str:
    """Escape a term for FTS5 query syntax."""
    # Quote terms that contain special characters
    if re.search(r'[^\w\u4e00-\u9fff-]', term):
        return f'"{term}"'
    return term


def load_registry(radioheader_dir: str) -> dict:
    """Load project-registry.json."""
    path = os.path.join(radioheader_dir, "project-registry.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def load_user_profile(radioheader_dir: str) -> dict:
    """Load user-profile.md and extract key fields."""
    path = os.path.join(radioheader_dir, "user-profile.md")
    if not os.path.exists(path):
        return {}
    try:
        text = open(path).read()
        profile = {}
        # Extract simple key-value pairs
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                key, _, val = line[2:].partition(":")
                profile[key.strip()] = val.strip()
        return profile
    except IOError:
        return {}


def compute_project_attention(query_terms: list, registry: dict, profile: dict) -> dict:
    """Compute attention weight for each project based on query context.

    Returns: {project_name: attention_score}
    """
    projects = registry.get("projects", [])
    if not projects:
        return {}

    scores = {}
    for proj in projects:
        name = proj["name"]
        status = proj.get("status", "active")

        # Archived/pending projects get minimal weight
        if status != "active":
            scores[name] = 0.1
            continue

        # Base weight from consolidate (default 1.0 = zero initialization)
        base = proj.get("attention_weight", 1.0)

        # Activity decay (pre-computed by consolidate, or from last_active)
        activity = proj.get("activity", 1.0)

        # Query-project relevance: overlap between query terms and project descriptors
        project_terms = set()
        for field_name in ("domains", "problems", "pain_points"):
            for term in proj.get(field_name, []):
                project_terms.add(term.lower())
        # Also add tech_stack tokens
        for token in proj.get("tech_stack", "").replace("+", ",").replace("(", ",").replace(")", "").split(","):
            t = token.strip().lower()
            if t:
                project_terms.add(t)

        # Compute overlap score
        overlap = 0
        for qt in query_terms:
            qt_lower = qt.lower()
            for pt in project_terms:
                if qt_lower in pt or pt in qt_lower:
                    overlap += 1
                    break  # count each query term at most once

        relevance = 1.0 + overlap * 0.5

        # User profile boost: check if query touches known weaknesses
        weaknesses = profile.get("weaknesses", "").lower()
        patterns = profile.get("patterns", "").lower()
        pain_points_text = " ".join(proj.get("pain_points", [])).lower()

        profile_boost = 1.0
        for qt in query_terms:
            qt_lower = qt.lower()
            if qt_lower in weaknesses or qt_lower in patterns or qt_lower in pain_points_text:
                profile_boost = 1.3
                break

        scores[name] = base * activity * relevance * profile_boost

    # Normalize: softmax-like normalization so scores sum to len(projects)
    total = sum(scores.values())
    if total > 0:
        n = len([s for s in scores.values() if s > 0])
        for name in scores:
            scores[name] = scores[name] / total * n

    return scores


def log_search(radioheader_dir: str, query: str, results: list, project_scores: dict):
    """Append search event to search-log.jsonl for consolidate analysis."""
    log_path = os.path.join(radioheader_dir, "search-log.jsonl")
    entry = {
        "ts": datetime.now().isoformat(),
        "query": query,
        "hit_count": len(results),
        "hit_projects": list(set(
            p for r in results[:10]
            for p in r.get("projects", "").split(", ") if p
        )),
        "attention_scores": {k: round(v, 3) for k, v in sorted(
            project_scores.items(), key=lambda x: -x[1]
        )[:5]} if project_scores else {},
    }
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except IOError:
        pass


def search(query: str, field: str = "", expand: bool = True, limit: int = 30,
           attention: bool = False) -> dict:
    """Search the FTS5 index."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return {"query": query, "terms": [], "expanded": [], "field": field,
                "count": 0, "results": [], "attention": False, "project_scores": {}}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Split query into terms (support | separator like grep)
    raw_terms = [t.strip() for t in re.split(r'\|', query) if t.strip()]

    # Expand synonyms if enabled
    if expand:
        all_terms = expand_synonyms(conn, raw_terms)
    else:
        all_terms = raw_terms

    # Build FTS5 query
    escaped = [fts5_escape(t) for t in all_terms]

    if field:
        # Field-specific search
        field_map = {
            "tags": "tags",
            "domain": "domain",
            "id": "id",
            "symptom": "symptom",
            "fix": "fix",
            "context": "context",
            "cause": "cause",
            "title": "title",
        }
        fts_field = field_map.get(field, field)
        fts_query = " OR ".join(f"{fts_field}:{t}" for t in escaped)
    else:
        # Full search across all fields with column weights
        # tags and symptom get higher weight via BM25
        fts_query = " OR ".join(escaped)

    # Check if projects column exists
    has_projects = False
    try:
        conn.execute("SELECT projects FROM entries LIMIT 1")
        has_projects = True
    except sqlite3.OperationalError:
        pass

    select_cols = "e.id, e.source, e.domain, e.tags, e.title, e.symptom, e.fix, e.file_path"
    if has_projects:
        select_cols += ", e.projects"

    try:
        # BM25 ranking: (id, domain, tags, title, symptom, fix, context, cause, body)
        # Weights: higher = more important
        rows = conn.execute(f"""
            SELECT
                {select_cols},
                bm25(entries_fts, 0, 2, 10, 5, 8, 3, 1, 1, 1) as rank
            FROM entries_fts
            JOIN entries e ON entries_fts.rowid = e.rowid
            WHERE entries_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit)).fetchall()
    except sqlite3.OperationalError:
        # Fallback: simpler query if FTS5 parsing fails
        simple_query = " OR ".join(f'"{t}"' for t in all_terms)
        try:
            rows = conn.execute(f"""
                SELECT
                    {select_cols},
                    bm25(entries_fts, 0, 2, 10, 5, 8, 3, 1, 1, 1) as rank
                FROM entries_fts
                JOIN entries e ON entries_fts.rowid = e.rowid
                WHERE entries_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (simple_query, limit)).fetchall()
        except sqlite3.OperationalError:
            conn.close()
            return {"query": query, "terms": raw_terms, "expanded": [], "field": field,
                    "count": 0, "results": [], "attention": False}

    results = []
    for row in rows:
        r = {
            "id": row["id"],
            "source": row["source"],
            "domain": row["domain"],
            "tags": row["tags"],
            "title": row["title"],
            "symptom": row["symptom"],
            "fix": row["fix"],
            "file_path": row["file_path"],
            "projects": row["projects"] if has_projects else "",
            "rank": round(row["rank"], 4),
        }
        results.append(r)

    conn.close()

    # --- Attention weighting ---
    rdir = os.environ.get("RADIOHEADER_DIR", os.path.expanduser("~/.claude/radioheader"))
    project_scores = {}

    if attention:
        registry = load_registry(rdir)
        profile = load_user_profile(rdir)
        project_scores = compute_project_attention(raw_terms, registry, profile)

        if project_scores:
            for r in results:
                entry_projects = [p.strip() for p in r["projects"].split(",") if p.strip()]
                if entry_projects:
                    # Take max project attention weight for this entry
                    max_weight = max(
                        project_scores.get(p, 1.0) for p in entry_projects
                    )
                else:
                    # No project association → neutral weight
                    max_weight = 1.0
                r["attention_weight"] = round(max_weight, 3)
                # BM25 rank is negative (lower = better), multiply by inverse of weight
                # so higher attention weight → lower (better) adjusted rank
                r["attention_rank"] = round(r["rank"] / max_weight, 4) if max_weight > 0 else r["rank"]

            # Re-sort by attention-adjusted rank
            results.sort(key=lambda x: x.get("attention_rank", x["rank"]))

    # Log search for consolidate analysis
    log_search(rdir, query, results, project_scores)

    # Add synonym expansion info
    expanded_terms = [t for t in all_terms if t not in raw_terms]

    return {
        "query": query,
        "terms": raw_terms,
        "expanded": expanded_terms,
        "field": field,
        "count": len(results),
        "results": results,
        "attention": attention,
        "project_scores": {k: round(v, 3) for k, v in sorted(
            project_scores.items(), key=lambda x: -x[1]
        )[:5]} if project_scores else {},
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RadioHeader FTS5 Search")
    parser.add_argument("query", help="Search query (supports | for OR)")
    parser.add_argument("--field", default="", help="Limit to specific field")
    parser.add_argument("--no-expand", action="store_true", help="Disable synonym expansion")
    parser.add_argument("--limit", type=int, default=30, help="Max results")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--attention", action="store_true", help="Enable attention-weighted ranking")
    args = parser.parse_args()

    result = search(args.query, field=args.field, expand=not args.no_expand,
                    limit=args.limit, attention=args.attention)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # Human-readable output
        if result["expanded"]:
            exp = ", ".join(result["expanded"])
            print(f"Synonyms expanded: +{exp}")
            print()

        if result["count"] == 0:
            print(f"No results for: {result['query']}")
            sys.exit(0)

        ranking_mode = "BM25 + Attention" if result.get("attention") else "BM25"
        print(f"Found {result['count']} result(s) ({ranking_mode}):")

        # Show top project attention scores if available
        if result.get("project_scores"):
            scores_str = ", ".join(f"{k}={v}" for k, v in result["project_scores"].items())
            print(f"  Project attention: {scores_str}")
        print()

        # Group by source
        by_source = {"shortwave": [], "community": [], "topic": []}
        for r in result["results"]:
            src = r["source"]
            if src in by_source:
                by_source[src].append(r)

        source_labels = {
            "shortwave": "📡 Shortwave (本地精炼)",
            "community": "🌐 Community (社区共享)",
            "topic": "📂 Topics (详细)",
        }

        for src, label in source_labels.items():
            entries = by_source.get(src, [])
            if not entries:
                continue
            print(f"  {label}:")
            for r in entries:
                title = r["title"] or r["id"]
                attn_info = ""
                if r.get("attention_weight") and r["attention_weight"] != 1.0:
                    attn_info = f" [attn: {r['attention_weight']:.2f}]"
                projects_info = ""
                if r.get("projects"):
                    projects_info = f" ({r['projects']})"
                print(f"    {r['id']}: {title}{attn_info}{projects_info}")
                if r["symptom"]:
                    symptom_preview = r["symptom"][:80]
                    print(f"      symptom: {symptom_preview}")
                print(f"      rank: {r['rank']}")
            print()
