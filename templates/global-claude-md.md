# --- RadioHeader START ---
# Do not manually edit this section. Managed by RadioHeader.
# https://github.com/ZaptainZ/radioheader

## Memory Reflux (All Projects) — MUST FOLLOW

**After completing a task series (bug fix, feature, deployment, etc.), MUST perform ALL of the following:**

1. Did this session produce new experience? (pitfalls, architecture decisions, non-obvious behavior)
2. If yes → update the corresponding topic file under `memory/`
3. Key experience → also update `memory/MEMORY.md` quick reference section
4. **Global reflux**: Is this experience useful across projects? If yes → write to `__HOME__/.claude/radioheader/topics/` with format `[source:ProjectName] experience content`
5. **Replace outdated info, don't append endlessly**

**Project documentation obligations (for projects with the dynamic experience framework):**

6. **Project info sync (MUST)**: If the project's architecture, key paths, tech stack, or important configurations changed during this session → MUST update the project overview document (the file listed as project overview in CLAUDE.md, typically `projectBasicInfo/01_PROJECT_OVERVIEW.md`). Do NOT skip this — stale project docs cause repeated re-exploration in future sessions.
7. **Task logs (MUST)**: If you completed a significant task (bug fix, feature development, architecture change, deployment, refactoring) → MUST write a log entry in the project's logs directory (typically `projectBasicInfo/logs/YYYY-MM-DD-topic-cc.md`). Content: background, goal, approach, modified files, issues encountered, conclusion. This is NOT optional for significant work.

**PROHIBITED**: Completing significant work without checking items 6 and 7. The PostToolUse hook will remind you when memory/ is updated, but you MUST also check proactively at the end of a task series.

> memory/ is under `~/.claude/projects/`, MEMORY.md first 200 lines auto-loaded per session.

## RadioHeader (Cross-Project Experience Hub) — MUST FOLLOW

Cross-project experience is stored in `__HOME__/.claude/radioheader/`, shared by all projects.

**Behavior rules (three steps, all mandatory):**

**Step 1: Search**. When facing a technical problem, MUST search RadioHeader first:
```
Grep pattern="keyword1|keyword2|keyword3" path="__HOME__/.claude/radioheader/shortwave/"
Grep pattern="keyword1|keyword2|keyword3" path="__HOME__/.claude/radioheader/topics/"
```
Use multiple synonymous keywords to increase hit rate (e.g. "white screen|slow launch|loading|startup").
**Shortwave entries take priority** — they are refined, project-agnostic knowledge. Use topics/ for additional detail when shortwave alone isn't enough.

**Step 2: Apply**. If relevant experience is found, MUST explicitly cite it in your response:
- Tell the user: "RadioHeader has relevant experience from {source project}: {summary}"
- Check each matching entry for applicability to the current problem
- If an entry points to a specific solution, **verify that solution's applicability first** before doing independent analysis

**Step 3: Trace**. If more details are needed, find the source project path from `project-registry.md`, then read its `memory/` directory for full context.

**PROHIBITED**: Finding relevant experience but not citing or applying it, jumping straight to independent analysis. RadioHeader's value is avoiding repeated pitfalls — finding but not using is the same as not searching.

- **Index**: `__HOME__/.claude/radioheader/INDEX.md`
- **Project registry**: `__HOME__/.claude/radioheader/project-registry.md`

## New Project Onboarding

**When entering a project, check if `.claude/rules/memory-reflux.md` exists in the project root.**

### If not found (new project)

Ask the user: "Would you like to enable the dynamic experience framework for this project?"

**If the user chooses yes**, collect the following:
1. Project name
2. Tech stack (e.g. iOS/SwiftUI, Java/Spring Boot, Vue 3, etc.)
3. Whether terminology mapping is needed (internal names ≠ user-facing names)
4. Documentation directory name (default: `projectBasicInfo`)

Then automatically create the project structure using templates from RadioHeader.

**Register new project**: After enabling the framework, also register the project in `__HOME__/.claude/radioheader/project-registry.md` (name, tech stack, path).

**If the user chooses not to enable**, work normally without creating extra files.

### If found (configured project)

Start working directly, following the project's CLAUDE.md and rules/.

# --- RadioHeader END ---
