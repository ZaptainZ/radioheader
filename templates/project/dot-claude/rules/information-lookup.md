# Information Lookup Strategy

> **This rule takes priority over default exploration behavior.** Follow these steps in order. Do not skip to Explore.

## Step 1: Check loaded context
MEMORY.md is auto-injected, rules/ are auto-loaded. Check if the needed information is already available.

## Step 2: Check CLAUDE.md document index
Look up the 1-2 relevant documents based on task type.

## Step 2.5: Search RadioHeader
```
Grep pattern="keyword" path="__HOME__/.claude/radioheader/topics/"
```
If more detail is needed → find the source project path from `project-registry.md` → read that project's `memory/` directory.

## Step 3: Use Grep/Glob for targeted search
Use search tools instead of Explore. Example: `Grep pattern="keyword" type="swift"`

## Step 4: Read matched files

## Step 5: Explore (last resort)
Only use when all above steps fail to locate information, and limit the search scope.
