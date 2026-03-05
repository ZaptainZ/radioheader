# Writing Good RadioHeader Entries

## Format

Each entry is a single Markdown list item:

```markdown
- [source:ProjectName] symptom/problem description — root cause explanation. Fix: solution
```

### Components

| Part | Purpose | Example |
|------|---------|---------|
| `[source:Name]` | Traceability — which project discovered this | `[source:MyApp]` |
| Symptom keywords | Searchability — what users actually search for | "white screen", "10s+ delay" |
| Root cause | Understanding — why it happens | "inherits Main Actor" |
| Fix | Action — what to do | "use `Task.detached(priority:)`" |

## Principles

### 1. Keep Symptom Keywords

Users search by **what they see**, not by **what the fix is**.

```markdown
# BAD — only has the solution
- [source:MyApp] Use Task.detached for iCloud operations

# GOOD — has the symptom, quantified data, AND the solution
- [source:MyApp] `Task {}` in `.onAppear` inherits Main Actor — iCloud I/O
  blocks main thread, causing 10s+ white screen (slow launch / startup delay).
  Fix: use `Task.detached(priority:)`
```

### 2. Add Synonyms

Different developers describe the same problem differently. Add synonyms in parentheses:

```markdown
- [source:MyApp] ... causing 10s+ white screen (slow launch / startup delay / 首次加载慢)
```

### 3. Include Quantified Data

"Slow" means different things to different people. Numbers are searchable and unambiguous:

```markdown
# BAD
- [source:MyApp] Debug mode causes slow launch

# GOOD
- [source:MyApp] Xcode "Debug executable" enabled → LLDB symbol loading causes
  20-40s white screen on iOS launch
```

### 4. One Entry Per Experience

Each line should be a complete, self-contained piece of knowledge:

```markdown
# BAD — multiple unrelated things in one entry
- [source:MyApp] NavigationStack has issues and also Swift concurrency is tricky
  and don't forget about safe areas

# GOOD — separate entries
- [source:MyApp] Nested NavigationStack inside outer NavigationStack →
  .navigationDestination stops working on iPad. Fix: remove inner NavigationStack
- [source:MyApp] `@MainActor` class's `deinit` is nonisolated — accessing
  non-Sendable properties requires `nonisolated(unsafe)`
```

### 5. Replace, Don't Append

When a better solution is found, **replace** the old entry. Don't keep both:

```markdown
# BAD — both versions kept
- [source:MyApp] Fix white screen by adding a loading view  ← outdated
- [source:MyApp] Fix white screen by using Task.detached    ← current

# GOOD — only the current solution
- [source:MyApp] `Task {}` in `.onAppear` inherits Main Actor — iCloud I/O
  blocks main thread, causing 10s+ white screen. Fix: Task.detached(priority:)
```

## Organizing Topic Files

Topic files are organized by technology or domain, not by project:

```
topics/
├── ios-swiftui.md          # iOS, SwiftUI, Xcode
├── rust-systems.md         # Rust, systems programming
├── backend-deploy.md       # Server, deployment, CI/CD
├── networking-proxy.md     # HTTP, proxy, certificates
├── ai-api-integration.md   # AI APIs, model integration
└── web-frontend.md         # Web, React, CSS
```

Create new topic files when an existing file doesn't cover a domain. Update `INDEX.md` when adding new files.

## Bilingual Entries

If you work in multiple languages, include keywords in both:

```markdown
- [source:MyApp] NavigationStack nested bug (嵌套导航栈 bug) — inner
  NavigationStack + outer → .navigationDestination breaks on iPad
```

This doubles the search surface without duplicating the entry.

## What NOT to Write

- **Trivial fixes**: "Typo in variable name" — not useful cross-project
- **Project-specific config**: "Our API key is stored in .env" — belongs in project memory
- **Already documented behavior**: Standard framework usage that's in official docs
- **Speculative solutions**: Only write what you've verified actually works
