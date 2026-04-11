#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path


RADIOHEADER_DIR = Path.home() / ".claude" / "radioheader"
SNAPSHOT_DIR = RADIOHEADER_DIR / ".codex-turn-snapshots"
# Hard cap on files walked from the project cwd. Huge monorepos (>100k files)
# would otherwise add ~1s+ and multi-MB snapshots per turn. Hitting the cap is
# fine: the Stop hook's hard blocks depend on memory/ and topics/shortwave/,
# which are walked via the candidates list and not subject to this limit.
REPO_WALK_FILE_LIMIT = 10000
# Keep snapshots from the last day to cover resumed sessions; discard older.
SNAPSHOT_TTL_SECONDS = 24 * 60 * 60
EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".claude",
    ".codex",
    "node_modules",
    "Pods",
    "build",
    "dist",
    ".next",
    ".turbo",
    "DerivedData",
    "__pycache__",
    ".venv",
    "venv",
}


def project_memory_dir(cwd: Path) -> Path:
    slug = "-" + str(cwd.resolve()).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory"


def discover_doc_dir(cwd: Path) -> Path | None:
    preferred = cwd / "projectBasicInfo"
    if preferred.is_dir():
        return preferred
    if not cwd.is_dir():
        return None
    try:
        children = list(cwd.iterdir())
    except OSError:
        return None
    for child in children:
        try:
            if child.is_dir() and (child / "00_AGENT_RULES.md").exists():
                return child
        except OSError:
            continue
    return None


def iter_repo_files(root: Path, limit: int = REPO_WALK_FILE_LIMIT):
    count = 0
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        current_path = Path(current_root)
        for filename in files:
            yield current_path / filename
            count += 1
            if count >= limit:
                return


def prune_stale_snapshots():
    if not SNAPSHOT_DIR.is_dir():
        return
    cutoff = time.time() - SNAPSHOT_TTL_SECONDS
    for snap in SNAPSHOT_DIR.glob("*.json"):
        try:
            if snap.stat().st_mtime < cutoff:
                snap.unlink()
        except OSError:
            pass


def tracked_files(cwd: Path):
    files = []
    doc_dir = discover_doc_dir(cwd)
    candidates = [
        cwd / "AGENTS.md",
        cwd / "CLAUDE.md",
        cwd / ".codex",
        cwd / ".claude",
        project_memory_dir(cwd),
        RADIOHEADER_DIR / "topics",
        RADIOHEADER_DIR / "shortwave",
        RADIOHEADER_DIR / "INDEX.md",
    ]
    if doc_dir is not None:
        candidates.append(doc_dir)
    for candidate in candidates:
        if not candidate.exists():
            continue
        if candidate.is_file():
            files.append(candidate)
            continue
        for path in candidate.rglob("*"):
            if path.is_file():
                files.append(path)
    for path in iter_repo_files(cwd):
        files.append(path)
    return sorted(set(files))


def snapshot_name(session_id: str, turn_id: str, cwd: str) -> Path:
    digest = hashlib.sha1(cwd.encode("utf-8")).hexdigest()[:12]
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SNAPSHOT_DIR / f"{session_id}-{turn_id}-{digest}.json"


def main():
    payload = json.load(os.fdopen(0))
    session_id = payload.get("session_id", "unknown")
    turn_id = payload.get("turn_id", "unknown")
    try:
        cwd = Path(payload["cwd"]).resolve()
    except (KeyError, OSError):
        return

    prune_stale_snapshots()

    try:
        doc_dir = discover_doc_dir(cwd)
    except OSError:
        doc_dir = None

    data = {
        "cwd": str(cwd),
        "doc_dir": str(doc_dir or ""),
        "memory_dir": str(project_memory_dir(cwd)),
        "files": {},
    }
    for path in tracked_files(cwd):
        try:
            stat = path.stat()
        except OSError:
            continue
        data["files"][str(path)] = {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}

    snapshot_path = snapshot_name(session_id, turn_id, str(cwd))
    with snapshot_path.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()
