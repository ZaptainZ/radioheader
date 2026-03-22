#!/usr/bin/env python3
"""
RadioHeader FTS5 Index Builder

Scans shortwave/, community/pool/, and topics/ directories,
parses Markdown frontmatter + body, and builds a SQLite FTS5 index.

Usage:
  python3 fts-index.py [--db PATH] [--radioheader-dir PATH]
  python3 fts-index.py --rebuild   # Force full rebuild
"""

import json
import os
import re
import sys
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime


def get_radioheader_dir():
    return os.environ.get("RADIOHEADER_DIR", os.path.expanduser("~/.claude/radioheader"))


def parse_shortwave(filepath: Path) -> dict:
    """Parse a shortwave .md file into structured fields."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    result = {
        "id": filepath.stem,
        "source": "",  # shortwave, community, topic
        "domain": "",
        "tags": "",
        "refs": "",
        "title": "",
        "symptom": "",
        "fix": "",
        "context": "",
        "cause": "",
        "body": "",
    }

    # Split frontmatter and body
    parts = text.split("---", 2)
    frontmatter = ""
    body = text
    if len(parts) >= 3:
        frontmatter = parts[1]
        body = parts[2]

    # Parse frontmatter fields
    for line in frontmatter.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "id":
                result["id"] = val
            elif key == "domain":
                result["domain"] = val
            elif key == "tags":
                result["tags"] = val
            elif key == "refs":
                result["refs"] = val

    # Parse body fields
    body_lines = body.strip().split("\n")
    current_field = None
    field_buffer = []

    for line in body_lines:
        stripped = line.strip()
        # Title (### heading)
        if stripped.startswith("### ") and not result["title"]:
            result["title"] = stripped[4:].strip()
            continue

        # Field detection (key: value or key:\n)
        field_match = re.match(r'^(symptom|symptoms|fix|context|cause|problem|solution):\s*(.*)', stripped, re.IGNORECASE)
        if field_match:
            # Save previous field
            if current_field and field_buffer:
                result[current_field] = "\n".join(field_buffer).strip()
                field_buffer = []
            current_field = field_match.group(1).lower()
            if current_field in ("symptoms", "problem"):
                current_field = "symptom"
            elif current_field == "solution":
                current_field = "fix"
            val = field_match.group(2).strip()
            if val:
                field_buffer.append(val)
            continue

        if current_field:
            field_buffer.append(stripped)

    # Save last field
    if current_field and field_buffer:
        result[current_field] = "\n".join(field_buffer).strip()

    result["body"] = body.strip()
    return result


def parse_topic(filepath: Path) -> list[dict]:
    """Parse a topic .md file into multiple entries (one per section)."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    topic_name = filepath.stem
    entries = []

    # Split by ## or ### headings
    sections = re.split(r'\n(?=##\s)', text)
    for i, section in enumerate(sections):
        if not section.strip():
            continue
        title_match = re.match(r'##\s+(.+)', section.strip())
        title = title_match.group(1) if title_match else f"{topic_name}_section_{i}"

        entry_id = f"topic-{topic_name}-{i}"
        entries.append({
            "id": entry_id,
            "source": "topic",
            "domain": topic_name,
            "tags": "",
            "refs": "",
            "title": title,
            "symptom": "",
            "fix": "",
            "context": "",
            "cause": "",
            "body": section.strip(),
        })

    return entries


# ============================================================
# Synonym table: Chinese ↔ English mapping
# ============================================================

SYNONYMS = [
    # UI/Display
    ("白屏", "blank screen", "white screen", "empty screen"),
    ("黑屏", "black screen"),
    ("闪退", "crash", "崩溃"),
    ("卡顿", "lag", "slow", "jank", "掉帧"),
    ("加载慢", "slow loading", "启动慢", "slow launch", "slow startup"),
    ("内存泄漏", "memory leak", "OOM", "out of memory"),
    # Navigation
    ("导航", "navigation", "路由", "routing"),
    ("返回", "back", "pop", "dismiss"),
    ("跳转", "navigate", "push", "redirect"),
    # Layout
    ("布局", "layout"),
    ("安全区", "safe area", "safearea"),
    ("键盘遮挡", "keyboard overlap", "keyboard covering"),
    ("滚动", "scroll", "scrollview"),
    # Network
    ("网络请求", "network request", "API call", "HTTP request"),
    ("超时", "timeout"),
    ("重试", "retry"),
    ("缓存", "cache", "caching"),
    # Data
    ("数据库", "database", "DB"),
    ("持久化", "persistence", "storage", "存储"),
    ("序列化", "serialization", "encoding", "解码", "decoding"),
    # State
    ("状态管理", "state management"),
    ("响应式", "reactive", "observable"),
    ("刷新", "refresh", "reload", "重新加载"),
    # Build/Deploy
    ("编译错误", "build error", "compile error"),
    ("签名", "signing", "codesign", "code signing"),
    ("打包", "build", "archive", "bundle"),
    ("发布", "release", "deploy", "publish"),
    # iOS specific
    ("预览崩溃", "preview crash", "SwiftUI preview"),
    ("模拟器", "simulator"),
    ("真机", "real device", "physical device"),
    ("权限", "permission", "entitlement"),
    # General
    ("配置", "configuration", "config", "设置", "settings"),
    ("日志", "log", "logging", "debug"),
    ("性能", "performance", "优化", "optimization"),
    ("并发", "concurrency", "async", "异步", "多线程", "multithreading"),
    ("动画", "animation"),
    ("手势", "gesture"),
    ("国际化", "i18n", "localization", "l10n", "本地化"),
]


def build_synonym_map() -> dict:
    """Build a mapping: term -> set of all synonyms (including itself)."""
    syn_map = {}
    for group in SYNONYMS:
        all_terms = set(t.lower() for t in group)
        for term in all_terms:
            if term not in syn_map:
                syn_map[term] = set()
            syn_map[term].update(all_terms - {term})
    return syn_map


def file_hash(filepath: Path) -> str:
    """Quick hash for change detection."""
    stat = filepath.stat()
    return hashlib.md5(f"{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()


def load_domain_index(radioheader_dir: str) -> dict:
    """Load domain→projects mapping from project-registry.json."""
    registry_path = os.path.join(radioheader_dir, "project-registry.json")
    if not os.path.exists(registry_path):
        return {}
    try:
        with open(registry_path) as f:
            data = json.load(f)
        return data.get("domain_index", {})
    except (json.JSONDecodeError, IOError):
        return {}


def resolve_projects(domain_str: str, domain_index: dict) -> str:
    """Map a domain string (e.g. 'iOS, SwiftUI, Navigation') to project names."""
    if not domain_str or not domain_index:
        return ""
    # Normalize: split by comma, lowercase, strip
    tokens = [t.strip().lower() for t in domain_str.replace("|", ",").split(",") if t.strip()]
    # Also try the raw domain as a slug (e.g. 'ios-swiftui' from topic source)
    tokens.append(domain_str.strip().lower())

    matched_projects = set()
    for token in tokens:
        if token in domain_index:
            matched_projects.update(domain_index[token])
        # Also try partial matching for compound domains
        for key in domain_index:
            if key in token or token in key:
                matched_projects.update(domain_index[key])

    return ", ".join(sorted(matched_projects))


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize the FTS5 database."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    # Main entries table (regular, for metadata)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id TEXT PRIMARY KEY,
            source TEXT,
            domain TEXT,
            tags TEXT,
            refs TEXT,
            title TEXT,
            symptom TEXT,
            fix TEXT,
            context TEXT,
            cause TEXT,
            body TEXT,
            file_path TEXT,
            file_hash TEXT,
            projects TEXT DEFAULT ''
        )
    """)

    # FTS5 virtual table for full-text search
    # content-sync with entries table
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
            id,
            domain,
            tags,
            title,
            symptom,
            fix,
            context,
            cause,
            body,
            content=entries,
            content_rowid=rowid,
            tokenize='unicode61'
        )
    """)

    # Synonym table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS synonyms (
            term TEXT NOT NULL,
            synonym TEXT NOT NULL,
            PRIMARY KEY (term, synonym)
        )
    """)

    # File tracking for incremental updates
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            file_path TEXT PRIMARY KEY,
            file_hash TEXT,
            updated_at TEXT
        )
    """)

    conn.commit()
    return conn


def upsert_entry(conn: sqlite3.Connection, entry: dict, file_path: str, fhash: str):
    """Insert or update an entry and its FTS index."""
    projects = entry.get("projects", "")

    # Check if entry exists and get rowid
    row = conn.execute("SELECT rowid FROM entries WHERE id = ?", (entry["id"],)).fetchone()

    if row:
        rowid = row[0]
        # Delete old FTS entry
        conn.execute("""
            INSERT INTO entries_fts(entries_fts, rowid, id, domain, tags, title, symptom, fix, context, cause, body)
            VALUES('delete', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rowid, entry["id"], entry["domain"], entry["tags"], entry["title"],
              entry["symptom"], entry["fix"], entry["context"], entry["cause"], entry["body"]))

        # Update entries table
        conn.execute("""
            UPDATE entries SET source=?, domain=?, tags=?, refs=?, title=?,
                   symptom=?, fix=?, context=?, cause=?, body=?, file_path=?, file_hash=?, projects=?
            WHERE id=?
        """, (entry["source"], entry["domain"], entry["tags"], entry["refs"], entry["title"],
              entry["symptom"], entry["fix"], entry["context"], entry["cause"], entry["body"],
              file_path, fhash, projects, entry["id"]))
    else:
        conn.execute("""
            INSERT INTO entries (id, source, domain, tags, refs, title, symptom, fix, context, cause, body, file_path, file_hash, projects)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (entry["id"], entry["source"], entry["domain"], entry["tags"], entry["refs"],
              entry["title"], entry["symptom"], entry["fix"], entry["context"], entry["cause"],
              entry["body"], file_path, fhash, projects))

    # Get new rowid and insert into FTS
    rowid = conn.execute("SELECT rowid FROM entries WHERE id = ?", (entry["id"],)).fetchone()[0]
    conn.execute("""
        INSERT INTO entries_fts(rowid, id, domain, tags, title, symptom, fix, context, cause, body)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (rowid, entry["id"], entry["domain"], entry["tags"], entry["title"],
          entry["symptom"], entry["fix"], entry["context"], entry["cause"], entry["body"]))


def populate_synonyms(conn: sqlite3.Connection):
    """Populate the synonym table."""
    conn.execute("DELETE FROM synonyms")
    syn_map = build_synonym_map()
    for term, syns in syn_map.items():
        for syn in syns:
            conn.execute("INSERT OR IGNORE INTO synonyms (term, synonym) VALUES (?, ?)", (term, syn))
    conn.commit()


def build_index(radioheader_dir: str, db_path: str, rebuild: bool = False):
    """Build or update the FTS5 index."""
    rdir = Path(radioheader_dir)
    shortwave_dir = rdir / "shortwave"
    community_pool = rdir / "community" / "pool"
    topics_dir = rdir / "topics"

    if rebuild and os.path.exists(db_path):
        os.remove(db_path)

    conn = init_db(db_path)

    # Ensure projects column exists (migration for existing DBs)
    try:
        conn.execute("SELECT projects FROM entries LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE entries ADD COLUMN projects TEXT DEFAULT ''")
        conn.commit()

    # Load domain→project mapping for project association
    domain_index = load_domain_index(radioheader_dir)

    # Scan directories
    scan_dirs = []
    if shortwave_dir.exists():
        scan_dirs.append(("shortwave", shortwave_dir))
    if community_pool.exists():
        scan_dirs.append(("community", community_pool))
    if topics_dir.exists():
        scan_dirs.append(("topic", topics_dir))

    total_indexed = 0
    total_skipped = 0
    total_removed = 0

    # Track all current file paths
    current_files = set()

    for source, directory in scan_dirs:
        for md_file in sorted(directory.glob("*.md")):
            fpath = str(md_file)
            current_files.add(fpath)
            fhash = file_hash(md_file)

            # Check if file has changed
            existing = conn.execute(
                "SELECT file_hash FROM file_index WHERE file_path = ?", (fpath,)
            ).fetchone()
            if existing and existing[0] == fhash and not rebuild:
                total_skipped += 1
                continue

            # Parse and index
            if source == "topic":
                entries = parse_topic(md_file)
                for entry in entries:
                    entry["source"] = source
                    entry["projects"] = resolve_projects(entry["domain"], domain_index)
                    upsert_entry(conn, entry, fpath, fhash)
                    total_indexed += 1
            else:
                entry = parse_shortwave(md_file)
                entry["source"] = source
                entry["projects"] = resolve_projects(entry["domain"], domain_index)
                upsert_entry(conn, entry, fpath, fhash)
                total_indexed += 1

            # Update file tracking
            conn.execute("""
                INSERT OR REPLACE INTO file_index (file_path, file_hash, updated_at)
                VALUES (?, ?, ?)
            """, (fpath, fhash, datetime.now().isoformat()))

    # Remove entries for deleted files
    tracked_files = conn.execute("SELECT file_path FROM file_index").fetchall()
    for (fpath,) in tracked_files:
        if fpath not in current_files:
            # Remove entries from this file
            entries_to_remove = conn.execute(
                "SELECT rowid, id, domain, tags, title, symptom, fix, context, cause, body FROM entries WHERE file_path = ?",
                (fpath,)
            ).fetchall()
            for row in entries_to_remove:
                rowid = row[0]
                conn.execute("""
                    INSERT INTO entries_fts(entries_fts, rowid, id, domain, tags, title, symptom, fix, context, cause, body)
                    VALUES('delete', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (rowid,) + row[1:])
                conn.execute("DELETE FROM entries WHERE rowid = ?", (rowid,))
                total_removed += 1
            conn.execute("DELETE FROM file_index WHERE file_path = ?", (fpath,))

    # Populate synonyms
    populate_synonyms(conn)

    conn.commit()

    # Stats
    total_entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    total_synonyms = conn.execute("SELECT COUNT(*) FROM synonyms").fetchone()[0]

    print(f"Index updated: {total_indexed} indexed, {total_skipped} unchanged, {total_removed} removed")
    print(f"Total: {total_entries} entries, {total_synonyms} synonym pairs")
    print(f"Database: {db_path} ({os.path.getsize(db_path) / 1024:.0f} KB)")

    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RadioHeader FTS5 Index Builder")
    parser.add_argument("--db", default=None, help="Database path")
    parser.add_argument("--radioheader-dir", default=None, help="RadioHeader directory")
    parser.add_argument("--rebuild", action="store_true", help="Force full rebuild")
    args = parser.parse_args()

    rdir = args.radioheader_dir or get_radioheader_dir()
    db = args.db or os.path.join(rdir, "search.db")

    build_index(rdir, db, rebuild=args.rebuild)
