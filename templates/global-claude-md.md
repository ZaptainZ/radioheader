# --- RadioHeader START ---
# Do not manually edit this section. Managed by RadioHeader.
# https://github.com/ZaptainZ/radioheader

## RadioHeader — Cross-Project Memory

A CLI-indexed knowledge base of pitfalls and solutions accumulated across this user's past projects, located at `~/.claude/radioheader/`. Auto-loaded summary is in `context-digest.md` (injected at session start); full index at `INDEX.md`.

**What's inside** (auto-indexed by `radioheader consolidate`):
- **Shortwave entries** — refined, project-agnostic experience snippets, one issue per file, with `symptoms / context / cause / fix` structure
- **Topic files** — domain-grouped depth (`ios-swiftui.md`, `rust-systems.md`, `networking-proxy.md`, `claude-code-meta.md`, etc.)
- **Project registry** — domains, pain points, attention weights, and source paths for every project the user works on (`project-registry.json` / `.md`)

**Primary query**: `radioheader search "<keywords>"` — FTS5 with BM25 ranking + Chinese/English synonym expansion (e.g. searching `白屏` auto-expands to `blank screen / white screen / empty screen`). Falls back to raw grep only if `search.db` is missing; prefer the CLI because synonym expansion catches entries you'd otherwise miss.

**When this is worth a search** (not a rule, just signals — judge based on the actual problem):
- User reports a concrete bug with reproducible symptoms (白屏 / 闪退 / 错位 / 数据丢失 / 慢)
- The problem feels domain-specific (iOS layout, Rust async, networking proxy, AI tool calling, hardware quirks)
- You're about to start non-trivial independent analysis on something the user has likely hit before
- A quick `radioheader search` (5 seconds) is much cheaper than redoing 30 minutes of debugging the user already did

**Search craft** — the difference between a useful search and a noise search:
- Search by **symptom words** (what's broken: `白屏`, `闪退`, `错位`, `丢失`, `慢`), not action words (`reply`, `click`, `请求`) — action words match everything and surface noise
- **Multi-symptom problems → use `|` (OR), not spaces**. `radioheader search "白屏|闪退"` runs OR with synonym expansion on both → ~18 hits. `radioheader search "白屏 闪退"` is AND-strict (both terms must appear in the same entry) → usually 0 hits. Spaces are the trap.
- **Chinese symptom words hit more often than English** — most entries are written in Chinese; an English query usually only matches via the predefined synonym table
- **No stemming** — `searched` won't match an entry tagged `search`/`搜索`/`搜到`; if the first form misses, try a different form (Chinese ↔ English, root word, near-synonym) before giving up
- Read the matched files. `search` returns content snippets; if you still need detail, `Read` the file
- If a generic word returns 15+ hits, narrow with `--field=tags` or `--field=symptom`, or use a more specific symptom word
- Reserve "search each symptom separately" for genuinely independent problems (e.g. user reports a UI bug *and* a network bug at once); for one underlying problem with multiple symptom expressions, prefer the `|` form
- One round of search per distinct problem is enough — don't loop searching the same library

**When you've found a hit**: cite the source project and entry summary in your response, verify it still applies (memory can be stale — files renamed, APIs changed), then apply. If you searched and found nothing relevant, just continue — no need to announce empty searches.

**Trace deeper context**: if a shortwave entry references a project's `memory/` for more, resolve the project path from `project-registry.json` and read that project's `memory/` directory.

## Echo (All Projects) — MUST FOLLOW

**After completing a task series (bug fix, feature, deployment, etc.), MUST perform ALL of the following:**

1. Did this session produce new experience? (pitfalls, architecture decisions, non-obvious behavior)
2. If yes → update the corresponding topic file under `memory/`
3. Key experience → also update `memory/MEMORY.md` quick reference section
4. **Global Echo**: Is this experience useful across projects? If yes → write to `/Users/zaptain/.claude/radioheader/topics/` with format `[source:ProjectName] experience content`
5. **Replace outdated info, don't append endlessly**

**Project documentation obligations (for projects with the dynamic experience framework):**

6. **Project info sync (MUST)**: If the project's architecture, key paths, tech stack, or important configurations changed during this session → MUST update the project overview document (the file listed as project overview in CLAUDE.md, typically `projectBasicInfo/01_PROJECT_OVERVIEW.md`). Do NOT skip this — stale project docs cause repeated re-exploration in future sessions.
7. **Task logs (MUST)**: If you completed a significant task (bug fix, feature development, architecture change, deployment, refactoring) → MUST write a log entry in the project's logs directory (typically `projectBasicInfo/logs/YYYY-MM-DD-topic-cc.md`). Content: background, goal, approach, modified files, issues encountered, conclusion. This is NOT optional for significant work.

**PROHIBITED**: Completing significant work without checking items 6 and 7. The PostToolUse hook will remind you when memory/ is updated, but you MUST also check proactively at the end of a task series.

> memory/ is under `~/.claude/projects/`, MEMORY.md first 200 lines auto-loaded per session.

## New Project Onboarding

**When entering a project, check if `.claude/rules/memory-echo.md` exists in the project root.**

### If not found (new project)

Ask the user ONE question only: "这是新项目，要启用 RadioHeader 动态经验框架吗？项目名默认用目录名，如果有正式名请告诉我。"

**If the user chooses yes**, only collect:
1. Project name (default: directory basename, user can override)

Tech stack, terminology mapping, and documentation directory are NOT asked upfront — they use defaults and evolve naturally:
- Tech stack: inferred from code as work progresses, written into `01_PROJECT_OVERVIEW.md` over time
- Terminology mapping: skipped by default, only added if the user later requests it
- Documentation directory: always `projectBasicInfo`

Then automatically create the project structure using templates from RadioHeader.

**Register new project**: After enabling the framework, also register the project in `/Users/zaptain/.claude/radioheader/project-registry.json` (and keep `project-registry.md` in sync via consolidate).

**If the user chooses not to enable**, work normally without creating extra files.

### If found (configured project)

Start working directly, following the project's CLAUDE.md and rules/.

# --- RadioHeader END ---
