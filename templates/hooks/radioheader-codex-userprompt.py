#!/usr/bin/env python3

import hashlib
import json
import os
from pathlib import Path


RADIOHEADER_DIR = Path.home() / ".claude" / "radioheader"
SNAPSHOT_DIR = RADIOHEADER_DIR / ".codex-turn-snapshots"
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
    for child in cwd.iterdir():
        if child.is_dir() and (child / "00_AGENT_RULES.md").exists():
            return child
    return None


def iter_repo_files(root: Path):
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        current_path = Path(current_root)
        for filename in files:
            yield current_path / filename


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
    cwd = Path(payload["cwd"]).resolve()

    data = {
        "cwd": str(cwd),
        "doc_dir": str(discover_doc_dir(cwd) or ""),
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
