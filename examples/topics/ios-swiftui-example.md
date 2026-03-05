# iOS / SwiftUI Cross-Project Experience (Example)

> Each entry is tagged `[source:ProjectName]` for traceability.
> This is an example file showing the recommended format and style.

## Concurrency & Actors

- [source:MyApp] `Task {}` created inside SwiftUI `.onAppear` / `body` **inherits Main Actor** — iCloud I/O still blocks main thread, causing **10s+ white screen** on iOS (common root cause for slow launch / white screen on first load). Must use `Task.detached(priority:)` to move off main thread
- [source:MyApp] Swift 6: `@MainActor` class's `deinit` is nonisolated — accessing non-Sendable properties (like CADisplayLink) requires `nonisolated(unsafe)`

## NavigationStack

- [source:AnotherApp] **Nested NavigationStack fatal bug**: Inner `NavigationStack{}` + outer NavigationStack → `.navigationDestination` stops working on iPad. Fix: remove inner NavigationStack
- [source:AnotherApp] After navigation pop, `@EnvironmentObject` may re-initialize → list state lost. Fix: use independent ViewModel to persist state

## Xcode & Build

- [source:MyApp] Xcode "Debug executable" enabled by default — LLDB symbol loading causes **20-40s white screen** on iOS (another common root cause for slow launch). Fix: set `debugEnabled: false` in project.yml scheme

## Key Principles for Writing Entries

1. **Keep symptom keywords**: "white screen", "slow launch", "10s+" — users search by symptoms, not solutions
2. **Include quantified data**: "20-40s" not just "slow"
3. **Add synonyms in parentheses**: "(slow launch / white screen on first load / startup delay)"
4. **Tag source project**: `[source:ProjectName]` enables tracing back for full context
5. **One line per experience**: concise but complete — root cause + solution
