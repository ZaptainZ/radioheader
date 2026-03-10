# Shortwave Quality Standards | 短波质量标准

This document defines what makes a good shortwave entry and provides a scoring rubric for auditing existing entries.

> 本文档定义短波条目的质量标准，提供评分规则用于审计已有条目。

## Four Dimensions | 四个维度

### 1. Searchability | 可搜性

Can the entry be found when someone hits this problem?

> 当有人遇到这个问题时，能搜到这条吗？

| Score | Criteria |
|-------|---------|
| ✅ Good | `tags` has symptom keywords + tech terms + Chinese/English synonyms; redundant with body |
| ⚠️ Weak | `tags` only has tech terms (e.g. "MainActor, Task") but no symptom words ("white screen", "白屏") |
| ❌ Bad | `tags` missing or has 1-2 generic words |

**Key rule**: People search by **what they see** ("app freezes", "白屏 10s"), not by **what the fix is** ("Task.detached"). Tags must cover both.

> 用户按**看到的现象**搜索，不按**解法**搜索。tags 必须覆盖两者。

### 2. Actionability | 可操作性

Can someone apply this knowledge immediately without further research?

> 看完能直接用吗？还是要再去查资料？

| Score | Criteria |
|-------|---------|
| ✅ Good | Has `cause` + `fix`, fix is specific and directly applicable |
| ⚠️ Weak | Has `fix` but it's vague ("refactor the code", "use a better approach") |
| ❌ Bad | Only describes the phenomenon, no cause or fix |

**Key rule**: `fix` must be a concrete action, not a direction. "Use `Task.detached(priority:)`" > "move I/O off the main thread".

> `fix` 必须是具体操作，不是方向建议。

### 3. Independence | 独立性

Can the entry be understood without reading the source project?

> 不看源项目也能看懂吗？

| Score | Criteria |
|-------|---------|
| ✅ Good | Self-contained; any developer in the same tech stack can understand it |
| ⚠️ Weak | Uses project-specific terms or assumes context not provided |
| ❌ Bad | Only makes sense if you know the source project's architecture |

**Key rule**: After stripping `[source:]`, the entry should still make complete sense to a stranger.

> 去掉 `[source:]` 后，陌生人也应该能完全看懂。

### 4. Precision | 精准性

Are the trigger conditions clear and specific?

> 触发条件是否明确具体？

| Score | Criteria |
|-------|---------|
| ✅ Good | Specific conditions: "Swift 6 + `@MainActor` class + `deinit` accessing non-Sendable property" |
| ⚠️ Weak | Partially specific: "Swift concurrency can cause issues in deinit" |
| ❌ Bad | Overly generic: "be careful with concurrency" |

**Key rule**: Specify **when** it happens, not just **what** happens. Include version, context, and trigger conditions.

> 不光写**发生了什么**，还要写**什么时候会发生**。

## Scoring | 评分

Each dimension scores: ✅ = 2, ⚠️ = 1, ❌ = 0. Total out of 8.

| Total | Grade | Action |
|-------|-------|--------|
| 7-8 | A | Keep as-is |
| 5-6 | B | Minor improvements (add missing tags, clarify fix) |
| 3-4 | C | Rewrite needed |
| 0-2 | D | Delete or rewrite from scratch |

## Audit Checklist | 审计清单

For each shortwave entry, check:

```
□ tags has ≥3 symptom/search terms (not just tech jargon)
□ tags has both Chinese and English keywords
□ cause is stated (not just symptoms)
□ fix is a specific action (not a vague suggestion)
□ context specifies when/where this occurs
□ No project-specific names, paths, or class names remain
□ Quantified data preserved (latency, size, frequency)
□ Entry makes sense without reading refs source
```

## Examples | 示例

### Grade A entry

```markdown
---
id: sw-ios-task-inherits-mainactor
domain: iOS, SwiftUI, Concurrency
tags: 白屏 | 启动慢 | 首次加载 | white screen | slow launch | 10s+ | hang | MainActor | Task | Task.detached
refs: topics/ios-swiftui.md
---
### Task {} 在 @MainActor 上下文中继承主线程，I/O 阻塞导致白屏

symptoms: 应用启动后 10s+ 白屏，首次加载卡死
context: SwiftUI `.onAppear` 或 `body` 中用 `Task {}` 发起 I/O 操作
cause: `Task {}` 继承调用者的 Actor 隔离；在 @MainActor 上下文中 = 主线程执行
fix: 改用 `Task.detached(priority: .userInitiated) { ... }`
verified: 启动白屏从 10s+ → <1s
```

✅ Searchable (symptoms in tags + body), ✅ Actionable (specific fix), ✅ Independent (no project refs), ✅ Precise (clear trigger conditions). Score: 8/8.

### Grade C entry (needs rewrite)

```markdown
---
id: sw-ios-navigation-issues
domain: iOS, SwiftUI
tags: NavigationStack
refs: topics/ios-swiftui.md
---
### NavigationStack 有一些坑

context: SwiftUI navigation
fix: 注意嵌套和状态管理
```

❌ Searchable (1 tag, no symptoms), ❌ Actionable (vague fix), ✅ Independent, ❌ Precise (no trigger conditions). Score: 2/8.

## When to Add a Case | 何时加案例

| Situation | Add case? |
|-----------|----------|
| `context + cause + fix` are specific and concrete | No — body is enough |
| Entry is abstract or principle-oriented | Yes — case makes it tangible |
| Symptoms are not intuitive for search | Yes — case provides searchable scenario |
| Entry spans multiple scenarios | Yes — case picks one representative scenario |

Case sections use pseudonymized details (see [shortwave-spec.md](shortwave-spec.md#pseudonymization-rules--假名化规则)).
