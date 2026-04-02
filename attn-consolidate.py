#!/usr/bin/env python3
"""
RadioHeader Attention Consolidate

Analyzes search logs and updates project attention weights in project-registry.json.
Like "sleep consolidation" in human memory — periodic compression of usage patterns
into stable attention weights.

Usage:
  python3 attn-consolidate.py
  python3 attn-consolidate.py --dry-run
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def get_radioheader_dir():
    return os.environ.get("RADIOHEADER_DIR", os.path.expanduser("~/.claude/radioheader"))


def load_registry(rdir: str) -> dict:
    path = os.path.join(rdir, "project-registry.json")
    if not os.path.exists(path):
        # Try to create it if parent dir exists
        parent = os.path.dirname(path)
        if os.path.isdir(parent):
            print(f"project-registry.json not found, creating empty one...")
            data = {"version": 1, "projects": [], "domain_index": {}}
            with open(path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            return data
        else:
            print(f"RadioHeader directory not found: {parent}", file=sys.stderr)
            print("Run 'radioheader' or install RadioHeader first.", file=sys.stderr)
            sys.exit(1)
    with open(path) as f:
        return json.load(f)


def load_search_log(rdir: str, days: int = 30) -> list:
    """Load recent search log entries."""
    path = os.path.join(rdir, "search-log.jsonl")
    if not os.path.exists(path):
        return []

    cutoff = datetime.now() - timedelta(days=days)
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts_str = entry.get("ts", "")
                # Parse ISO timestamp
                try:
                    ts = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    continue
                if ts >= cutoff:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries


def load_error_log(rdir: str, days: int = 30) -> list:
    """Load recent error log entries."""
    path = os.path.join(rdir, "error-log.jsonl")
    if not os.path.exists(path):
        return []

    cutoff = datetime.now() - timedelta(days=days)
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts_str = entry.get("ts", "")
                try:
                    ts = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    continue
                if ts >= cutoff:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries


def analyze_error_patterns(error_log: list) -> dict:
    """Analyze error log for recurring patterns, grouped by project (cwd).

    Returns: {cwd: [{pattern, count, snippet, first_seen, last_seen}]}
    """
    # Group by (cwd, pattern)
    from collections import Counter
    pattern_counts = defaultdict(lambda: defaultdict(list))

    for entry in error_log:
        cwd = entry.get("cwd", "unknown")
        pattern = entry.get("pattern", "")
        if pattern:
            pattern_counts[cwd][pattern].append(entry)

    result = {}
    for cwd, patterns in pattern_counts.items():
        recurring = []
        for pattern, entries in patterns.items():
            if len(entries) >= 2:  # Only flag if it happened 2+ times
                timestamps = [e.get("ts", "") for e in entries]
                recurring.append({
                    "pattern": pattern,
                    "count": len(entries),
                    "snippet": entries[-1].get("snippet", ""),
                    "first_seen": min(timestamps) if timestamps else "",
                    "last_seen": max(timestamps) if timestamps else "",
                })
        if recurring:
            result[cwd] = sorted(recurring, key=lambda x: -x["count"])

    return result


def compute_activity_decay(last_active: str, today: datetime) -> float:
    """Compute activity score based on last_active date.

    Decay curve: 1.0 at day 0, 0.5 at day 30, 0.2 at day 90.
    """
    if not last_active:
        return 0.1

    try:
        last = datetime.fromisoformat(last_active)
    except (ValueError, TypeError):
        try:
            last = datetime.strptime(last_active, "%Y-%m-%d")
        except (ValueError, TypeError):
            return 0.1

    days_ago = (today - last).days
    if days_ago <= 0:
        return 1.0
    elif days_ago <= 7:
        return 0.95
    elif days_ago <= 14:
        return 0.85
    elif days_ago <= 30:
        return 0.7
    elif days_ago <= 60:
        return 0.5
    elif days_ago <= 90:
        return 0.3
    else:
        return 0.2


def rebuild_domain_index(projects: list) -> dict:
    """Rebuild domain_index from project domains."""
    index = defaultdict(list)
    for proj in projects:
        name = proj["name"]
        for domain in proj.get("domains", []):
            if name not in index[domain]:
                index[domain].append(name)
    return dict(index)


def generate_readable_registry(registry: dict, rdir: str):
    """Generate human-readable project-registry.md from JSON."""
    projects = registry.get("projects", [])
    lines = [
        "# 项目注册表",
        "",
        "> 所有使用 Claude Code 管理的项目。新项目启用 RadioHeader 时应在此注册。",
        "> 此文件由 `radioheader consolidate` 自动生成，源数据在 `project-registry.json`。",
        "",
        "| 项目名 | 技术栈 | 状态 | 活跃度 | 注意力权重 | 搜索命中 |",
        "|--------|--------|------|--------|-----------|---------|",
    ]
    for p in projects:
        name = p["name"]
        tech = p.get("tech_stack", "-")
        status = p.get("status", "active")
        activity = f"{p.get('activity', 1.0):.1f}"
        attn = f"{p.get('attention_weight', 1.0):.2f}"
        hits = str(p.get("search_hits", 0))
        status_map = {"active": "活跃", "archived": "归档", "pending": "待定"}
        status_cn = status_map.get(status, status)
        lines.append(f"| {name} | {tech} | {status_cn} | {activity} | {attn} | {hits} |")

    lines.append("")

    # Detailed project cards
    lines.append("## 项目详情")
    lines.append("")
    for p in projects:
        if p.get("status") != "active":
            continue
        lines.append(f"### {p['name']}")
        lines.append(f"- 角色: {p.get('user_role', '-')}")
        lines.append(f"- 领域: {', '.join(p.get('domains', []))}")
        lines.append(f"- 问题: {', '.join(p.get('problems', []))}")
        if p.get("pain_points"):
            lines.append(f"- 痛点: {', '.join(p['pain_points'])}")
        lines.append("")

    md_path = os.path.join(rdir, "project-registry.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))


def load_user_profile(rdir: str) -> dict:
    """Load user-profile.md and extract key fields."""
    path = os.path.join(rdir, "user-profile.md")
    if not os.path.exists(path):
        return {}
    profile = {}
    try:
        for line in open(path).read().split("\n"):
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                key, _, val = line[2:].partition(":")
                profile[key.strip()] = val.strip()
    except IOError:
        pass
    return profile


# Budget for context-digest (chars). Claude Code truncates instruction files
# at ~4,000 chars each. We target 3,500 to leave headroom for loader delimiters.
MAX_DIGEST_CHARS = 3500


def generate_context_digest(rdir: str, registry: dict, search_log: list,
                            error_patterns: dict, today: datetime):
    """Generate context-digest.md — compressed environmental awareness for Agent.

    This is where attention mechanism produces its output:
    instead of weighting search results per-query,
    it compresses the user's project landscape, recent focus,
    and behavioral patterns into a digest that gets loaded at session start.
    """
    projects = registry.get("projects", [])
    profile = load_user_profile(rdir)

    # --- Attention analysis: what has the user been focused on? ---

    # Recent search topics (last 30 days)
    recent_queries = [e.get("query", "") for e in search_log[-50:]]
    query_freq = defaultdict(int)
    for q in recent_queries:
        for term in q.lower().replace("|", " ").split():
            if len(term) >= 2:
                query_freq[term] += 1
    top_queries = sorted(query_freq.items(), key=lambda x: -x[1])[:10]

    # Active projects (sorted by activity)
    active = sorted(
        [p for p in projects if p.get("status") == "active"],
        key=lambda p: -(p.get("activity", 0))
    )

    # Projects with most search hits
    hot_projects = sorted(
        [p for p in projects if p.get("search_hits", 0) > 0],
        key=lambda p: -(p.get("search_hits", 0))
    )[:5]

    # --- Generate digest ---
    lines = [
        "# 环境认知摘要",
        "",
        f"> 由 `radioheader consolidate` 于 {today.strftime('%Y-%m-%d')} 生成。",
        "> 每次记忆同步时自动更新。Agent 通过此文件理解用户的整体环境。",
        "",
    ]

    # User profile summary
    if profile:
        lines.append("## 用户特征")
        lines.append("")
        if profile.get("problem_solving"):
            lines.append(f"- 解决问题方式: {profile['problem_solving']}")
        if profile.get("strengths"):
            lines.append(f"- 长处: {profile['strengths']}")
        if profile.get("weaknesses"):
            lines.append(f"- 短板: {profile['weaknesses']}")
        if profile.get("patterns"):
            lines.append(f"- 反复出现的模式: {profile['patterns']}")
        if profile.get("devices"):
            lines.append(f"- 设备: {profile['devices']}")
        if profile.get("network"):
            lines.append(f"- 网络: {profile['network']}")
        lines.append("")

    # Active project landscape
    lines.append("## 项目全景")
    lines.append("")
    for p in active[:8]:
        name = p["name"]
        role = p.get("user_role", "")
        problems = ", ".join(p.get("problems", []))
        pain = ", ".join(p.get("pain_points", []))
        activity = p.get("activity", 0)
        hits = p.get("search_hits", 0)

        # Activity indicator
        if activity >= 0.9:
            indicator = "活跃"
        elif activity >= 0.7:
            indicator = "近期"
        elif activity >= 0.5:
            indicator = "偶尔"
        else:
            indicator = "低频"

        line = f"- **{name}** ({indicator})"
        if role:
            line += f" — {role}"
        lines.append(line)
        # Scope annotation: project path for Agent navigation
        proj_path = p.get("path", "")
        if proj_path:
            lines.append(f"  scope: `{proj_path}`")
        if problems:
            lines.append(f"  关注: {problems}")
        if pain:
            lines.append(f"  痛点: {pain}")
    lines.append("")

    # Recent focus (from search log)
    if top_queries:
        lines.append("## 近期关注")
        lines.append("")
        focus_terms = ", ".join(f"{term}({count})" for term, count in top_queries)
        lines.append(f"搜索热词: {focus_terms}")
        lines.append("")

    if hot_projects:
        lines.append("搜索命中最多的项目:")
        for p in hot_projects:
            lines.append(f"- {p['name']}: {p.get('search_hits', 0)} 次命中")
        lines.append("")

    # Cross-project patterns (the "dark thread")
    # Find domains that appear in 3+ projects
    domain_spread = defaultdict(list)
    for p in active:
        for d in p.get("domains", []):
            domain_spread[d].append(p["name"])
    shared_domains = {d: ps for d, ps in domain_spread.items() if len(ps) >= 3}

    if shared_domains:
        lines.append("## 跨项目技术交叉")
        lines.append("")
        for domain, proj_names in sorted(shared_domains.items(), key=lambda x: -len(x[1])):
            lines.append(f"- **{domain}**: {', '.join(proj_names)}")
        lines.append("")

    # Recurring error patterns (project-level issues to record)
    if error_patterns:
        lines.append("## 反复出现的问题（需要记录到项目记忆中）")
        lines.append("")
        lines.append("> 以下错误在多次会话中重复出现。请检查对应项目的 CLAUDE.md 或 MEMORY.md，")
        lines.append("> 将结构性事实（如 git 仓库路径、构建命令、环境依赖）记录下来，避免反复探索。")
        lines.append("")

        # Try to map cwd to project name
        project_map = {}
        for p in registry.get("projects", []):
            proj_path = os.path.expanduser(p.get("path", ""))
            if proj_path:
                project_map[proj_path.rstrip("/")] = p["name"]

        for cwd, patterns in error_patterns.items():
            # Find project name from cwd
            proj_name = "未知项目"
            cwd_clean = cwd.rstrip("/")
            for proj_path, name in project_map.items():
                if cwd_clean.startswith(proj_path) or proj_path.startswith(cwd_clean):
                    proj_name = name
                    break

            lines.append(f"**{proj_name}** (`{cwd}`):")
            for p in patterns:
                label_map = {
                    "not-a-git-repo": "git 仓库不在此目录",
                    "file-not-found": "文件/路径不存在",
                    "command-not-found": "命令未安装",
                    "permission-denied": "权限不足",
                    "network-error": "网络连接问题",
                }
                label = label_map.get(p["pattern"], p["pattern"])
                lines.append(f"- {label} ({p['count']} 次): `{p['snippet']}`")
            lines.append("")

    # --- Budget-aware truncation ---
    content = "\n".join(lines)
    if len(content) > MAX_DIGEST_CHARS:
        # Drop sections from bottom (lowest priority) until within budget
        # Section markers: ## headers
        section_splits = content.split("\n## ")
        # First part is the header (always keep)
        rebuilt = section_splits[0]
        for part in section_splits[1:]:
            candidate = rebuilt + "\n## " + part
            if len(candidate) <= MAX_DIGEST_CHARS:
                rebuilt = candidate
            else:
                break
        content = rebuilt.rstrip() + "\n\n> [digest truncated — budget %d chars]" % MAX_DIGEST_CHARS

    # Write digest
    digest_path = os.path.join(rdir, "context-digest.md")
    with open(digest_path, "w") as f:
        f.write(content)

    return digest_path


def consolidate(rdir: str, dry_run: bool = False):
    """Main consolidation logic."""
    registry = load_registry(rdir)
    projects = registry.get("projects", [])
    search_log = load_search_log(rdir)
    error_log = load_error_log(rdir)
    error_patterns = analyze_error_patterns(error_log)
    today = datetime.now()

    error_info = f", {len(error_log)} errors" if error_log else ""
    print(f"Consolidating {len(projects)} projects, {len(search_log)} recent searches{error_info}...")

    if error_patterns:
        total_recurring = sum(len(ps) for ps in error_patterns.values())
        print(f"  Found {total_recurring} recurring error pattern(s) across {len(error_patterns)} project(s)")

    # 1. Count project hits from search log
    project_hits = defaultdict(int)
    for entry in search_log:
        for proj in entry.get("hit_projects", []):
            project_hits[proj] += 1

    # 2. Update each project
    changes = []
    for proj in projects:
        name = proj["name"]
        old_activity = proj.get("activity", 1.0)
        old_weight = proj.get("attention_weight", 1.0)
        old_hits = proj.get("search_hits", 0)

        # Update activity from last_active decay
        new_activity = compute_activity_decay(proj.get("last_active"), today)

        # Update search_hits
        new_hits = old_hits + project_hits.get(name, 0)

        # Update attention_weight: blend of activity + hit frequency
        # Zero initialization principle: starts at 1.0, adjusts based on evidence
        hit_bonus = min(project_hits.get(name, 0) * 0.1, 0.5)  # cap at +0.5
        new_weight = new_activity * (1.0 + hit_bonus)

        # Archived projects stay low
        if proj.get("status") != "active":
            new_weight = min(new_weight, 0.5)

        proj["activity"] = round(new_activity, 2)
        proj["attention_weight"] = round(new_weight, 3)
        proj["search_hits"] = new_hits

        if (abs(new_activity - old_activity) > 0.01 or
                abs(new_weight - old_weight) > 0.01 or
                new_hits != old_hits):
            changes.append(f"  {name}: activity {old_activity:.2f}→{new_activity:.2f}, "
                           f"weight {old_weight:.3f}→{new_weight:.3f}, "
                           f"hits {old_hits}→{new_hits}")

    # 3. Rebuild domain_index
    registry["domain_index"] = rebuild_domain_index(projects)

    if changes:
        print("Changes:")
        for c in changes:
            print(c)
    else:
        print("No changes needed.")

    if dry_run:
        print("\n[dry-run] No files modified.")
        return

    # 4. Write updated registry
    registry_path = os.path.join(rdir, "project-registry.json")
    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Updated: {registry_path}")

    # 5. Generate readable .md
    generate_readable_registry(registry, rdir)
    md_path = os.path.join(rdir, "project-registry.md")
    print(f"Generated: {md_path}")

    # 6. Trim old search log entries (keep last 90 days)
    log_path = os.path.join(rdir, "search-log.jsonl")
    if os.path.exists(log_path):
        cutoff = today - timedelta(days=90)
        kept = 0
        lines = []
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry.get("ts", ""))
                    if ts >= cutoff:
                        lines.append(line)
                        kept += 1
                except (json.JSONDecodeError, ValueError):
                    pass
        with open(log_path, "w") as f:
            f.write("\n".join(lines) + "\n" if lines else "")
        print(f"Search log: kept {kept} entries (trimmed to 90 days)")

    # 7. Generate context digest (the actual attention output)
    digest_path = generate_context_digest(rdir, registry, search_log, error_patterns, today)
    print(f"Generated: {digest_path}")

    # 8. Trim error log (keep last 30 days — errors are more ephemeral than searches)
    error_log_path = os.path.join(rdir, "error-log.jsonl")
    if os.path.exists(error_log_path):
        cutoff = today - timedelta(days=30)
        kept = 0
        lines = []
        with open(error_log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry.get("ts", ""))
                    if ts >= cutoff:
                        lines.append(line)
                        kept += 1
                except (json.JSONDecodeError, ValueError):
                    pass
        with open(error_log_path, "w") as f:
            f.write("\n".join(lines) + "\n" if lines else "")
        if error_log:
            print(f"Error log: kept {kept} entries (trimmed to 30 days)")

    print("Done.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RadioHeader Attention Consolidate")
    parser.add_argument("--radioheader-dir", default=None, help="RadioHeader directory")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without modifying files")
    args = parser.parse_args()

    rdir = args.radioheader_dir or get_radioheader_dir()
    consolidate(rdir, dry_run=args.dry_run)
