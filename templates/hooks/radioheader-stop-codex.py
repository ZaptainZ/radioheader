#!/usr/bin/env python3

from __future__ import annotations

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


def iter_repo_files(root: Path, limit: int = 10000):
    # Mirror the UserPromptSubmit hook's file cap so before/after snapshots
    # walk the same set; otherwise large repos would produce massive
    # false-positive diffs.
    count = 0
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        current_path = Path(current_root)
        for filename in files:
            yield current_path / filename
            count += 1
            if count >= limit:
                return


def tracked_files(cwd: Path, doc_dir: Path | None, memory_dir: Path):
    files = []
    candidates = [
        cwd / "AGENTS.md",
        cwd / "CLAUDE.md",
        cwd / ".codex",
        cwd / ".claude",
        memory_dir,
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
    return SNAPSHOT_DIR / f"{session_id}-{turn_id}-{digest}.json"


def collect_state(cwd: Path, doc_dir: Path | None, memory_dir: Path):
    state = {}
    for path in tracked_files(cwd, doc_dir, memory_dir):
        try:
            stat = path.stat()
        except OSError:
            continue
        state[str(path)] = {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}
    return state


def changed_paths(before, after):
    changes = []
    all_paths = set(before) | set(after)
    for path in sorted(all_paths):
        if before.get(path) != after.get(path):
            changes.append(path)
    return changes


def is_under(path: Path, parent: Path | None) -> bool:
    if parent is None:
        return False
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def shorten(path: Path, cwd: Path) -> str:
    home = Path.home()
    try:
        return f"./{path.relative_to(cwd)}"
    except ValueError:
        pass
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)


def summarize_paths(paths, cwd: Path, limit: int = 3) -> str:
    if not paths:
        return ""
    preview = [shorten(Path(p), cwd) for p in paths[:limit]]
    if len(paths) > limit:
        preview.append(f"+{len(paths) - limit} more")
    return ", ".join(preview)


def main():
    payload = json.load(os.fdopen(0))
    session_id = payload.get("session_id", "unknown")
    turn_id = payload.get("turn_id", "unknown")
    cwd = Path(payload["cwd"]).resolve()
    stop_hook_active = bool(payload.get("stop_hook_active"))

    if stop_hook_active:
        print(json.dumps({"continue": True}))
        return

    snapshot_path = snapshot_name(session_id, turn_id, str(cwd))
    if not snapshot_path.exists():
        # No baseline (e.g. UserPromptSubmit hook did not fire, or the
        # snapshot was purged). Without a baseline every file looks "new",
        # which would spam blocking messages. Exit quietly instead.
        print(json.dumps({"continue": True}))
        return

    snapshot = {}
    before = {}
    with snapshot_path.open() as f:
        snapshot = json.load(f)
        before = snapshot.get("files", {})

    doc_dir_raw = snapshot.get("doc_dir") or ""
    memory_dir_raw = snapshot.get("memory_dir") or ""
    doc_dir = Path(doc_dir_raw) if doc_dir_raw else discover_doc_dir(cwd)
    memory_dir = Path(memory_dir_raw) if memory_dir_raw else project_memory_dir(cwd)

    after = collect_state(cwd, doc_dir, memory_dir)
    changes = changed_paths(before, after)

    topic_root = RADIOHEADER_DIR / "topics"
    shortwave_root = RADIOHEADER_DIR / "shortwave"
    index_file = RADIOHEADER_DIR / "INDEX.md"
    overview_file = doc_dir / "01_PROJECT_OVERVIEW.md" if doc_dir else None
    logs_dir = doc_dir / "logs" if doc_dir else None
    claude_dir = cwd / ".claude"
    claude_rules_dir = cwd / ".claude" / "rules"
    codex_dir = cwd / ".codex"

    topic_changes = [p for p in changes if is_under(Path(p), topic_root)]
    shortwave_changes = [p for p in changes if is_under(Path(p), shortwave_root)]
    index_changes = [p for p in changes if Path(p) == index_file]
    memory_changes = [p for p in changes if is_under(Path(p), memory_dir)]
    overview_changes = [p for p in changes if overview_file and Path(p) == overview_file]
    log_changes = [p for p in changes if is_under(Path(p), logs_dir)]
    rule_changes = [p for p in changes if is_under(Path(p), claude_rules_dir)]
    runtime_changes = [
        p
        for p in changes
        if Path(p) in {cwd / "AGENTS.md", cwd / "CLAUDE.md"}
        or is_under(Path(p), codex_dir)
        or is_under(Path(p), claude_dir)
    ]
    project_doc_changes = [
        p
        for p in changes
        if doc_dir
        and is_under(Path(p), doc_dir)
        and not is_under(Path(p), logs_dir)
        and (overview_file is None or Path(p) != overview_file)
    ]
    source_changes = [
        p
        for p in changes
        if is_under(Path(p), cwd)
        and not is_under(Path(p), doc_dir)
        and not is_under(Path(p), claude_rules_dir)
        and not is_under(Path(p), codex_dir)
        and Path(p) not in {cwd / "AGENTS.md", cwd / "CLAUDE.md"}
    ]

    if snapshot_path.exists():
        snapshot_path.unlink(missing_ok=True)

    follow_up = []
    messages = []

    if memory_changes and not topic_changes:
        follow_up.append(
            "Project memory changed this turn, but no global RadioHeader topic was updated. "
            "Review the new project-specific memory and echo any reusable cross-project experience into "
            "~/.claude/radioheader/topics/. If you add a new topic file, also update ~/.claude/radioheader/INDEX.md."
        )

    if topic_changes and not shortwave_changes:
        topic_preview = summarize_paths(topic_changes, cwd)
        extra = f" Changed topics: {topic_preview}." if topic_preview else ""
        follow_up.append(
            "Global RadioHeader topics changed this turn, but no shortwave entry was updated. "
            "Distill the new cross-project experience into the corresponding shortwave entry before stopping."
            + extra
        )

    if follow_up:
        print(json.dumps({"decision": "block", "reason": "\n\n".join(follow_up)}))
        return

    if (cwd / ".claude" / "rules" / "memory-echo.md").exists():
        messages.append(
            "Session Echo checklist: new experience -> memory/topics; architecture or key path changes -> update project overview; significant completed work -> write logs."
        )
    if topic_changes and not index_changes:
        messages.append(
            "RadioHeader topics changed. If this turn created a new topic file, update ~/.claude/radioheader/INDEX.md."
        )
    if memory_changes:
        messages.append(f"Project memory changed: {summarize_paths(memory_changes, cwd)}.")
    if shortwave_changes:
        messages.append(f"Shortwave updated: {summarize_paths(shortwave_changes, cwd)}.")
    if overview_changes:
        messages.append("Project overview changed this turn.")
    if runtime_changes or rule_changes:
        messages.append(
            "Project instructions changed. Verify the overview still reflects the current architecture and operating rules."
        )
    if source_changes and not log_changes and doc_dir:
        messages.append(
            f"Code or config files changed ({summarize_paths(source_changes, cwd)}). If this completed significant work, write a log under {shorten(logs_dir, cwd)}."
        )
    if project_doc_changes and not overview_changes and doc_dir:
        messages.append(
            f"Project docs changed ({summarize_paths(project_doc_changes, cwd)}). Update {shorten(overview_file, cwd)} if architecture or key paths changed."
        )
    if log_changes:
        messages.append(f"Project logs changed: {summarize_paths(log_changes, cwd)}.")
    if (RADIOHEADER_DIR / "community" / "pool").is_dir():
        messages.append("If you used community entries, evaluate causal contribution and append votes.")

    output = {"continue": True}
    if messages:
        output["systemMessage"] = " ".join(messages)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
