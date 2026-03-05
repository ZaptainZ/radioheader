# Shortwave Specification | 知识短波规范

Shortwave is RadioHeader's distilled experience layer. Each shortwave entry is a **project-agnostic**, **searchable** knowledge unit extracted from project-specific experience in `topics/`.

> 知识短波是 RadioHeader 的精炼经验层。每条短波条目是从 `topics/` 中的项目级经验提炼出的**项目无关**、**可搜索**的知识单元。

## Format | 格式

```yaml
---
id: sw-{domain-abbrev}-{number}
domain: comma-separated, no limit (e.g. iOS, SwiftUI, Concurrency)
tags: symptom keywords | tech terms | synonyms (Chinese + English, redundant with body for search)
refs: source file(s) in topics/ (optional, loss doesn't affect functionality)
---
```

### Title line | 标题行

Use `###` heading — one sentence summarizing the pattern or rule.

> 用 `###` 标题——一句话概括规律。

### Body | 正文

Key-value pairs, freely organized. Common keys:

| Key | Purpose | 用途 |
|-----|---------|------|
| `symptoms` | Observable behaviors that trigger diagnosis | 可观察的触发诊断的行为 |
| `context` | When/where this occurs | 何时/何处发生 |
| `cause` | Root cause | 根因 |
| `fix` | Solution or mitigation | 解决方案 |

Keys are suggestions, not mandatory. Add or remove as needed.

> key 是建议，不是强制。按需增减。

### Case section (conditional) | Case 段（条件性添加）

**Add a case when**: the entry is abstract, principle-oriented, or the symptoms are not intuitive enough for search.

**Do NOT add a case when**: context + cause + fix are already specific and actionable.

> **何时加 case**：条目偏抽象、偏原则、或症状不够直观时。
> **何时不加**：context + cause + fix 已足够具体可操作时。

Case content uses pseudonymized details (see Pseudonymization Rules below).

## Example | 示例

```markdown
---
id: sw-ios-0003
domain: iOS, SwiftUI, Concurrency
tags: white screen | slow launch | startup delay | 白屏 | 启动慢 | 加载卡住 | MainActor | Task | onAppear
refs: ios-swiftui.md
---

### Task {} in SwiftUI .onAppear inherits MainActor — I/O blocks main thread

context: SwiftUI view's `.onAppear` runs on MainActor. `Task {}` inside it inherits actor context.
symptoms: 10s+ white screen on launch, app appears frozen, no crash
cause: Synchronous or actor-inherited I/O (e.g. CloudKit, file reads) blocks the main thread
fix: Use `Task.detached(priority:)` or explicit `nonisolated` function for I/O work
```

## Refinement Rules (5+1 Steps) | 精炼规则（5+1 步）

When distilling a `topics/` entry into a shortwave entry:

> 将 `topics/` 条目精炼为短波条目时：

### Step 1: Strip project bindings | 剥离项目绑定

Remove project names, file paths, specific variable/class names that are project-specific.

> 移除项目名、文件路径、项目特有的变量/类名。

### Step 2: Abstract to universal pattern | 抽象为通用规律

Transform "changed Y in file X" → "in scenario Z, symptom W occurs".

> 将"在 X 文件改了 Y" → "在 Z 场景下会出现 W 症状"。

### Step 3: Complete domain and tags | 补全 domain 和 tags

- `domain`: comma-separated technology areas
- `tags`: Chinese + English symptom keywords, tech terms, synonyms. **Intentionally redundant with body** — this maximizes search hit rate.

> domain 用逗号分隔技术领域。tags 包含中英文症状词、技术名词、同义表述，**与正文保持冗余**以提高搜索命中率。

### Step 4: Preserve symptom keywords and quantified data | 保留症状关键词和量化数据

Never strip symptoms to leave only the solution. Users search by symptoms, not by solutions.

> 不能只留解法而丢掉症状。用户按症状搜索，不按解法搜索。

### Step 5: Supplement diagnostic information | 补充诊断信息

If the original entry omits information that aids diagnosis (e.g. common misdiagnoses, misleading symptoms), add it.

> 如果原始条目缺少有助于诊断的信息（如常见误判、误导性症状），补充上去。

### Step 6 (conditional): Generate pseudonymized case | （条件判断）生成假名化案例

**When to add**: The entry is abstract, principle-oriented, or symptoms are not intuitive.

**When to skip**: context + cause + fix are already specific and actionable.

> **何时加**：条目偏抽象、偏原则、或症状不够直观。
> **何时不加**：context + cause + fix 已足够具体可操作。

## Pseudonymization Rules | 假名化规则

When creating case sections, apply these transformations:

| Original | Replacement | 规则 |
|----------|-------------|------|
| Project name | Usage description ("a journaling app") | 项目名 → 用途描述 |
| Generic class names (e.g. `ViewController`) | Keep as-is | 通用类名保留 |
| Project-specific class names | Replace or remove | 专有类名替换或删除 |
| Data content | Substitute with common equivalents | 数据内容 → 同类常见物替代 |
| Quantified data (10s+, 40MB) | Keep as-is | 量化数据原样保留 |
| Device/environment (generic) | Keep as-is | 通用设备/环境保留 |

## File Naming | 文件命名

```
sw-{domain-abbrev}-{4-digit-number}.md
```

Examples:
- `sw-ios-0001.md`
- `sw-rust-0001.md`
- `sw-claude-code-0001.md`

Domain abbreviation should be the primary/most specific domain. Number is sequential within that domain.

> domain 缩写取最主要/最具体的领域。编号在该领域内递增。

## Directory | 目录

Shortwave entries are stored in `~/.claude/radioheader/shortwave/`.

> 短波条目存放在 `~/.claude/radioheader/shortwave/`。

## Search Priority | 搜索优先级

When both shortwave and topics results are found:

1. **Shortwave first** — more refined, project-agnostic, directly applicable
2. **Topics for detail** — when shortwave summary isn't enough, trace to topics/ for richer context
3. **Source project memory/** — when topics/ isn't enough, trace to source project via `refs` or `project-registry.md`

> 搜到短波和 topics 结果时：短波优先（更精炼）→ topics 补细节 → 源项目 memory/ 追溯。
