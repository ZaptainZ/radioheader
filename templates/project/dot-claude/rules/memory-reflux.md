# Memory Reflux Rules

After completing a task series, the agent must check if new experience should be recorded.

## When to Record
- Fixed a bug (record root cause and correct approach)
- Made an architecture decision (record choice and reasoning)
- Discovered non-obvious behavior (things not in docs but encountered in practice)

## Where to Write

### Project-level reflux
- Specific experience → topic files under `memory/`
- Key experience → also update `MEMORY.md` quick reference section

### Global reflux (cross-project experience)
- Ask: Is this experience useful for other projects?
- General technical experience → `__HOME__/.claude/radioheader/topics/` under the corresponding topic file
- Format: `[source:ProjectName] experience content`
- Also update `__HOME__/.claude/radioheader/INDEX.md` entry count

## How to Write
- Replace outdated information, don't append endlessly
- One experience per line + necessary context
- Don't repeat procedures already documented in project docs
