# Log Writing Rules

`__DOC_DIR__/logs/` stores important implementation plans and outcome records.

## When to Write

- **When starting a major plan**: Write a planning doc with goals, approach, and affected files
- **After completing a major plan**: Write an outcome doc with what was done, issues encountered, and final approach
- **When the user requests it**: Follow this rule when prompted

## Naming Format

`YYYY-MM-DD-english-topic-role.md`

Example: `2026-02-08-auth-system-design-cc.md`

## Principles

- Logs are **implementation records**, not project documentation. Project docs go in `__DOC_DIR__/` main directory
- One plan = one log file (if planning and outcome are separate, use same date with different suffixes)
- Content includes: background, goals, approach, modified files, issues encountered, conclusions
- Agent should proactively write at the start and end of major work, without waiting for user prompts
