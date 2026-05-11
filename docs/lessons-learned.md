# Lessons Learned

RadioHeader was developed through real-world usage across 13 projects. This document records what we tried, what failed, and what works.

## Lesson 1: "Searched But Didn't Use"

**The problem**: Early RadioHeader told Claude to "search RadioHeader when facing a technical problem." Claude would dutifully search, find 3 topic files with 4 matching lines, and then completely ignore all of it — proceeding with independent analysis from scratch.

**Why it happened**: The runtime rule only specified the **search** action, not what to do with the results. The agent treated the search as a checkbox to tick, not as input to its analysis.

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

**The problem**: The first version of RadioHeader's runtime instruction section was informational:

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

**Takeaway**: In `CLAUDE.md` / `AGENTS.md`, every instruction that should drive behavior must be phrased as a mandate with "MUST", "ALWAYS", or "PROHIBITED". Informational descriptions create awareness, not action.

## Lesson 4: Session Hooks Provide Critical Context

**The problem**: Even with rules in the runtime instruction file, the agent sometimes "forgot" about RadioHeader because the rules were buried in a long file.

**The fix**: A SessionStart hook that prints:

```
📡 RadioHeader ready (7 topic files)
   Search: Grep pattern="keyword" path="~/.claude/radioheader/topics/"
   Index: ~/.claude/radioheader/INDEX.md
```

This provides a visible, session-start reminder that RadioHeader exists and how to use it.

**Takeaway**: Runtime rules set the behavior; hooks reinforce it with timely context.

## Lesson 5: New Project Detection Enables Organic Growth

**The problem**: If RadioHeader only works for projects that are manually configured, adoption stalls. Users set up their first few projects and then forget.

**The fix**: A SessionStart hook that checks for `.claude/rules/memory-echo.md` in the project root. If missing, it prompts: "This project has not configured the dynamic experience framework." Claude then asks the user if they want to enable it.

**Takeaway**: Passive detection + active prompting creates organic adoption without manual intervention.

## Lesson 6: Project Registry Enables Tracing

**The problem**: A RadioHeader entry says `[source:MyApp]` — but where is MyApp? What's its path? What other context does its memory/ have?

**The fix**: `project-registry.json` stores project names, filesystem paths, and metadata; `project-registry.md` is the human-readable projection. When the agent needs to trace an experience back to its source, it resolves the path there and reads the source project's memory files.

**Takeaway**: Source tagging is only useful if there's a way to resolve the tag to a location.

## Lesson 7: Replace, Don't Append

**The problem**: Over time, topic files accumulate outdated entries. Multiple entries describe the same problem with increasingly better solutions, but the old entries remain.

**The fix**: The Echo rule explicitly states "Replace outdated information, don't append endlessly." When a better solution is found, the old entry is updated in place.

**Takeaway**: Curation is more important than accumulation. A smaller, accurate knowledge base is more valuable than a larger one with stale entries.

## Lesson 8: The Instruction Must Match the Tool's Actual Behavior

**The problem**: The SessionStart loader once told agents `Search: Grep pattern="keyword" path="topics/"`. Agents dutifully ran a single broad `Grep`, got dozens of file names with no snippets, and skipped the result as background noise. Meanwhile, the actual tool — `radioheader search`, with FTS5 + bilingual synonym expansion — was never mentioned. The instruction was teaching a degraded fallback, not the real entry point.

**Why it kept failing in layers**: Fixing the loader exposed deeper layers:

- **L1 — Wrong tool name**: instruction said `Grep`, not `radioheader search`. Agents followed the instruction literally and missed FTS5 entirely.
- **L2 — Strong-imperative drag**: even after pointing at the right CLI, `MUST search / PROHIBITED to ignore` framing produced ritual searches (run-and-skip) rather than judgment-based use.
- **L3 — The CLI silently broken**: `radioheader search` itself failed under any user with a legacy `/usr/local/bin/python3` 3.6.x ahead of newer interpreters on PATH — Python 3.6 doesn't support `from __future__ import annotations`, which the FTS5 helper requires.
- **L4 — Wrong query syntax in the docs**: even with a working CLI, instructions suggested space-separated multi-symptom queries (`"白屏 闪退"`). FTS5 defaults to AND-strict; that query returns 0. The correct multi-symptom syntax is OR pipe: `"白屏|闪退"` (~18 hits with synonym expansion on both terms).

**The fixes** (applied as a stack):

1. **Loader teaches the real tool**: `radioheader search "<symptom>"` with a one-line value statement, not a fallback `Grep`.
2. **`CLAUDE.md` / `AGENTS.md` "search" section uses descriptive language** (what's inside, when it's worth searching, search craft signals) instead of `MUST` / `PROHIBITED`. Echo and onboarding remain strong-imperative because skipping them is asymmetrically destructive.
3. **CLI auto-resolves Python ≥ 3.7**: a `_resolve_py3` wrapper in the `radioheader` script tries `python3`, then `/usr/bin/python3`, then `/opt/homebrew/bin/python3`, then `python3.{11,10,9}` — picking the first interpreter that satisfies the version requirement. Override with `RH_PY_OVERRIDE` if needed.
4. **OR pipe documented as the primary multi-symptom syntax**: `radioheader search "A|B"` runs OR with synonym expansion on every term. Space-separated queries are explicitly marked as the trap they are.

**Takeaways**:

- The instruction surface (loader output + `CLAUDE.md` rules) is part of the tool, not metadata around it. If the docs say `Grep` and the actual entry point is FTS5, agents follow the docs and the tool's strength is invisible.
- Trusting LLM judgment requires the tool description to be **literally correct and runnable** — listing the command, what's inside, when it's worth running, and the syntax traps. Strong imperatives are no substitute for an accurate map.
- When a layer of fix uncovers a deeper layer (loader → docs → CLI runtime → query syntax), the bug isn't "the LLM didn't try hard enough" — it's that the previous layer was masking the next.

## Anti-Patterns to Avoid

1. **Making RadioHeader a database**: It's a collection of text files searched with `Grep`. Don't add schemas, APIs, or query languages.

2. **Over-categorizing topics**: A few broad topic files (ios-swiftui.md, backend-deploy.md) work better than dozens of narrow ones. Grep doesn't care about file boundaries.

3. **Writing entries for machines**: Entries should be human-readable. They're consumed by an LLM that understands natural language — not parsed by a structured query engine.

4. **Automating Echo completely**: The agent's judgment about "is this useful cross-project?" is critical. Fully automated extraction produces noise.

5. **Treating RadioHeader as documentation**: It's experience, not documentation. Docs describe how things should work. RadioHeader describes what actually happens when things don't work as documented.
