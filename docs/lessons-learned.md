# Lessons Learned

RadioHeader was developed through real-world usage across 13 projects. This document records what we tried, what failed, and what works.

## Lesson 1: "Searched But Didn't Use"

**The problem**: Early RadioHeader told Claude to "search RadioHeader when facing a technical problem." Claude would dutifully search, find 3 topic files with 4 matching lines, and then completely ignore all of it — proceeding with independent analysis from scratch.

**Why it happened**: The CLAUDE.md rule only specified the **search** action, not what to do with the results. Claude treated the search as a checkbox to tick, not as input to its analysis.

**The fix**: Replace the single "search" instruction with a three-step mandatory behavioral rule:

1. **Search** — with multiple synonymous keywords
2. **Apply** — explicitly cite found experience in the response
3. **Trace** — follow up to source project if needed

Plus an explicit prohibition: "Finding relevant experience but not citing or applying it is PROHIBITED."

**Takeaway**: For LLM behavioral rules, specify the entire workflow — not just the trigger action. Every step between input and output must be explicitly mandated.

## Lesson 2: Symptom Keywords Get Stripped

**The problem**: When extracting experience from project memory files into RadioHeader topic files, the natural tendency is to write clean, solution-focused entries. But this strips the symptom keywords that users actually search for.

**Example**: A project memory entry said:

```
Task {} in .onAppear inherits Main Actor — iCloud I/O causes 10s+ white screen on first load
```

The extracted RadioHeader entry became:

```
Use Task.detached for iCloud operations to avoid blocking main thread
```

When a user later searched "white screen" or "首次加载慢", the sanitized entry didn't match.

**The fix**: Keep symptom keywords and add synonyms in parentheses:

```
[source:MyApp] Task {} in .onAppear inherits Main Actor — iCloud I/O blocks main
thread, causing 10s+ white screen (slow launch / startup delay / 首次加载慢).
Fix: Task.detached(priority:)
```

**Takeaway**: Write entries for the searcher, not the reader. Symptoms are how people find entries; solutions are what they find.

## Lesson 3: Instructions Beat Knowledge

**The problem**: The first version of RadioHeader's CLAUDE.md section was informational:

```
## RadioHeader (Cross-Project Experience Hub)
Cross-project experience is stored in ~/.claude/radioheader/.
You can search topics/ when facing technical problems.
```

Claude treated this as background information — nice to know, optional to act on.

**The fix**: Rewrite as imperative behavioral instructions:

```
## RadioHeader — MUST FOLLOW
**Step 1: Search.** When facing a technical problem, MUST search RadioHeader first:
...
**PROHIBITED**: Finding relevant experience but not citing or applying it.
```

**Takeaway**: In CLAUDE.md, every instruction that should drive behavior must be phrased as a mandate with "MUST", "ALWAYS", or "PROHIBITED". Informational descriptions create awareness, not action.

## Lesson 4: Session Hooks Provide Critical Context

**The problem**: Even with rules in CLAUDE.md, Claude sometimes "forgot" about RadioHeader because the rules were buried in a long file.

**The fix**: A SessionStart hook that prints:

```
📡 RadioHeader ready (7 topic files)
   Search: Grep pattern="keyword" path="~/.claude/radioheader/topics/"
   Index: ~/.claude/radioheader/INDEX.md
```

This provides a visible, session-start reminder that RadioHeader exists and how to use it.

**Takeaway**: CLAUDE.md rules set the behavior; hooks reinforce it with timely context.

## Lesson 5: New Project Detection Enables Organic Growth

**The problem**: If RadioHeader only works for projects that are manually configured, adoption stalls. Users set up their first few projects and then forget.

**The fix**: A SessionStart hook that checks for `.claude/rules/memory-reflux.md` in the project root. If missing, it prompts: "This project has not configured the dynamic experience framework." Claude then asks the user if they want to enable it.

**Takeaway**: Passive detection + active prompting creates organic adoption without manual intervention.

## Lesson 6: Project Registry Enables Tracing

**The problem**: A RadioHeader entry says `[source:MyApp]` — but where is MyApp? What's its path? What other context does its memory/ have?

**The fix**: `project-registry.md` maps project names to filesystem paths and tech stacks. When Claude needs to trace an experience back to its source, it looks up the path and reads the source project's memory files.

**Takeaway**: Source tagging is only useful if there's a way to resolve the tag to a location.

## Lesson 7: Replace, Don't Append

**The problem**: Over time, topic files accumulate outdated entries. Multiple entries describe the same problem with increasingly better solutions, but the old entries remain.

**The fix**: The reflux rule explicitly states "Replace outdated information, don't append endlessly." When a better solution is found, the old entry is updated in place.

**Takeaway**: Curation is more important than accumulation. A smaller, accurate knowledge base is more valuable than a larger one with stale entries.

## Anti-Patterns to Avoid

1. **Making RadioHeader a database**: It's a collection of text files searched with `Grep`. Don't add schemas, APIs, or query languages.

2. **Over-categorizing topics**: A few broad topic files (ios-swiftui.md, backend-deploy.md) work better than dozens of narrow ones. Grep doesn't care about file boundaries.

3. **Writing entries for machines**: Entries should be human-readable. They're consumed by an LLM that understands natural language — not parsed by a structured query engine.

4. **Automating reflux completely**: The agent's judgment about "is this useful cross-project?" is critical. Fully automated extraction produces noise.

5. **Treating RadioHeader as documentation**: It's experience, not documentation. Docs describe how things should work. RadioHeader describes what actually happens when things don't work as documented.
