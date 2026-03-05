# RadioHeader

**Cross-project experience sharing for Claude Code.**
**Claude Code 跨项目经验共享框架。**

RadioHeader gives Claude Code a persistent memory layer that works across all your projects. When you solve a tricky bug in Project A, that experience automatically becomes available in Project B, C, and every future project.

> RadioHeader 为 Claude Code 提供跨项目的持久记忆层。在项目 A 中解决的棘手 bug，其经验会自动在项目 B、C 以及所有未来项目中可用。

## The Problem | 问题

Claude Code's memory is isolated per project. You fix a SwiftUI NavigationStack bug in one app, then hit the exact same issue three months later in another app — and Claude starts from scratch.

RadioHeader solves this by creating a shared experience hub that Claude searches before analyzing any technical problem.

> Claude Code 的记忆按项目隔离。你在一个 app 中修了 NavigationStack 的 bug，三个月后在另一个 app 中遇到同样问题——Claude 从零开始。RadioHeader 创建共享经验中枢，Claude 在分析技术问题前会先搜索这里。

## How It Works | 工作原理

```
┌─────────────────────────────────────────────────┐
│                  RadioHeader                     │
│                                                  │
│  shortwave/  (refined, project-agnostic)         │
│    sw-ios-0001.md · sw-rust-0001.md · ...        │
│                                                  │
│  topics/  (detailed, with [source:] tags)        │
│    ios-swiftui.md · rust-systems.md · ...        │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┼────────────────┐
        ▼            ▼                ▼
   ┌─────────┐ ┌─────────┐     ┌─────────┐
   │Project A│ │Project B│     │Project N│
   │ memory/ │ │ memory/ │     │ memory/ │
   └─────────┘ └─────────┘     └─────────┘
```

**Three-layer memory model | 三层记忆模型：**

1. **RadioHeader** (global) — cross-project experience, shared by all projects | 跨项目经验，所有项目共享
2. **Project memory** (`~/.claude/projects/*/memory/`) — project-specific context | 项目特定上下文
3. **Session context** — ephemeral, within one conversation | 临时，仅在单次对话中

**Behavioral rules — Search, Apply, Trace | 行为规则 — 搜→用→追：**

1. **Search | 搜**: When facing a technical problem, Claude searches RadioHeader first | 遇到技术问题时先搜索 RadioHeader
2. **Apply | 用**: If relevant experience is found, Claude cites and applies it | 找到相关经验后必须引用并应用
3. **Trace | 追**: If more detail is needed, Claude traces back to the source project's memory | 需要更多细节时追溯到源项目

This isn't optional — RadioHeader injects mandatory behavioral rules into Claude's CLAUDE.md, so the agent **must** search, apply, and trace. Finding experience but not using it is explicitly prohibited.

> 这不是可选的——RadioHeader 在 CLAUDE.md 中注入强制性行为规则。找到经验但不使用是被明确禁止的。

## Installation | 安装

### Prerequisites | 前置条件

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed (`~/.claude/` directory exists)
- `jq` recommended for automatic settings.json merging (`brew install jq` / `apt install jq`)

### Install | 安装

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh
```

The installer | 安装器会：
- Creates `~/.claude/radioheader/` with index and registry files | 创建索引和注册文件
- Installs 4 hooks into `~/.claude/hooks/` | 安装 4 个 hook 脚本
- Appends RadioHeader behavioral rules to `~/.claude/CLAUDE.md` | 追加行为规则到 CLAUDE.md
- Merges hooks into `~/.claude/settings.json` (SessionStart + PostToolUse + Stop) | 合并 hooks 配置
- Copies project templates for `radioheader init` | 复制项目模板供 CLI 使用
- Installs `radioheader` CLI to `/usr/local/bin/` (or `~/bin/` fallback) | 安装 CLI 工具
- Creates timestamped backups of all modified files | 为所有修改文件创建带时间戳的备份

### Uninstall | 卸载

```bash
cd radioheader
./uninstall.sh
```

Removes all RadioHeader components. If you have topic files, it will ask before deleting them.

> 移除所有 RadioHeader 组件。如果有经验文件，会在删除前询问。

## CLI | 命令行工具

RadioHeader includes a CLI for project initialization and daily management:

> RadioHeader 包含一个 CLI 工具，用于项目初始化和日常管理：

```bash
radioheader init      # Initialize current project | 初始化当前项目
radioheader search    # Search topics | 搜索经验
radioheader status    # Show status | 显示状态
radioheader doctor    # Health check | 健康检查
radioheader align     # Topics↔shortwave coverage | 覆盖率分析与批量精炼
radioheader help      # Show help | 显示帮助
```

### `radioheader init`

Initialize the dynamic experience framework in your current project directory:

> 在当前项目目录中初始化动态经验框架：

```bash
# Interactive mode (prompts for each value) | 交互模式
radioheader init

# Flag mode | 参数模式
radioheader init --name "MyApp" --stack "iOS/SwiftUI"
radioheader init --name "MyApp" --stack "Python/FastAPI" --doc-dir docs --terms "internal=external"
```

This creates the project scaffolding (`CLAUDE.md`, `.claude/rules/`, doc directory) and registers the project. Existing files are never overwritten.

> 创建项目脚手架（CLAUDE.md、.claude/rules/、文档目录）并注册项目。已存在的文件不会被覆盖。

### `radioheader search`

Search across all topic files:

> 搜索所有经验文件：

```bash
radioheader search "NavigationStack"
radioheader search "white screen|slow launch|startup"
```

### `radioheader status`

Show topic file count, entry count, registered projects, and installation health:

> 显示主题文件数、条目数、注册项目数和安装状态：

```bash
radioheader status
```

### `radioheader doctor`

Run comprehensive health checks — hooks, CLAUDE.md markers, topic tags, INDEX consistency, stale registry entries:

> 运行全面健康检查——hooks、CLAUDE.md 标记、topic 标签、INDEX 一致性、过时注册条目：

```bash
radioheader doctor
```

### `radioheader align`

Analyze coverage between topics and shortwave, then batch refine uncovered entries:

> 分析 topics 与 shortwave 的覆盖率，批量精炼未覆盖的条目：

```bash
# Coverage report (analysis only) | 覆盖率报告（仅分析）
radioheader align

# Output batch refinement instructions as additionalContext JSON | 输出批量精炼指令
radioheader align --execute

# Validate and fix shortwave refs links | 校验并修复 refs 链接
radioheader align --refs
```

**`--execute` mode** outputs a structured `additionalContext` JSON that Claude reads in-session to batch-create shortwave entries for all uncovered topic entries. It includes all topic entries, existing shortwave list, refinement rules, and naming conventions.

> **`--execute` 模式**输出结构化 JSON，Claude 在会话中读取后批量创建 shortwave 条目。包含所有 topic 条目、已有 shortwave 列表、精炼规则和命名规范。

## Usage | 使用

### Automatic (just work normally) | 自动模式

After installation, RadioHeader works automatically:

> 安装后自动工作：

1. **Session start | 会话开始**: A hook fires showing "RadioHeader ready (N topic files)" | 显示就绪状态
2. **New project detection | 新项目检测**: Claude asks if you want to enable the dynamic experience framework | 询问是否启用动态经验框架
3. **Problem solving | 问题解决**: Claude searches RadioHeader before investigating | 先搜索 RadioHeader 再分析
4. **Memory sync | 记忆联动**: PostToolUse hook detects memory/ writes and triggers reflux checks | PostToolUse hook 检测 memory 写入并触发回流
5. **Experience reflux | 经验回流**: After completing a task series, Claude checks if experience should flow back | 完成任务后检查是否需要回流
6. **Shortwave refinement | 短波精炼**: When topics/ is updated, a hook triggers Claude to distill entries into project-agnostic shortwave entries in `shortwave/` | 更新 topics/ 时自动触发精炼为项目无关的短波条目

### Shortwave (Knowledge Distillation) | 知识短波

Shortwave is a refined layer on top of topics. Each shortwave entry strips project-specific details and abstracts the experience into a universal, searchable knowledge unit.

> 短波是 topics 之上的精炼层。每条短波去除项目细节，抽象为通用可搜索的知识单元。

- **Automatic**: PostToolUse hook triggers refinement when topics/ is updated | 自动触发
- **Searchable**: `radioheader search` shows shortwave results first | 搜索时短波优先显示
- **Project-agnostic**: No project names, paths, or specific class names | 不含项目名、路径、专有类名
- **Format**: YAML frontmatter (id, domain, tags) + key-value body | YAML 元数据 + 键值对正文

See [`docs/shortwave-spec.md`](docs/shortwave-spec.md) for the full specification.

> 详见 [`docs/shortwave-spec.md`](docs/shortwave-spec.md)。

### Writing Experience Entries | 编写经验条目

Experience accumulates naturally as you work. Entries are written to topic files under `~/.claude/radioheader/topics/`:

> 经验在工作中自然积累，写入 `~/.claude/radioheader/topics/` 下的主题文件：

```markdown
- [source:MyApp] `Task {}` in SwiftUI `.onAppear` inherits Main Actor —
  iCloud I/O blocks main thread, causing 10s+ white screen (slow launch /
  startup delay). Fix: use `Task.detached(priority:)`
```

**Key principles | 关键原则：**

- Keep **symptom keywords** ("white screen", "slow launch", "10s+") — users search by symptoms | 保留症状关键词——用户按症状搜索
- Include **quantified data** ("20-40s" not just "slow") | 包含量化数据
- Add **synonyms** in parentheses for search discoverability | 添加同义词提高搜索命中率
- Tag **source project** `[source:Name]` for traceability | 标注源项目用于追溯
- One experience per line — concise but complete | 一条经验一行

See [`examples/topics/`](examples/topics/) for a full example.

### Per-Project Setup | 项目级配置

Use `radioheader init` or let Claude offer to set up the dynamic experience framework when you open a project for the first time. This creates:

> 使用 `radioheader init` 或在首次打开项目时让 Claude 提供启用选项。创建以下结构：

```
your-project/
├── .claude/
│   ├── settings.json         # Project-level hooks | 项目级 hooks
│   ├── hooks/
│   │   └── load-project-rules.sh
│   └── rules/
│       ├── memory-reflux.md  # Experience reflux rules | 经验回流规则
│       ├── logs-writing.md   # Log writing rules | 日志写入规则
│       └── information-lookup.md  # Search strategy | 信息查找策略
├── CLAUDE.md                 # Project entry point | 项目入口
└── {doc-dir}/
    ├── 00_AGENT_RULES.md
    ├── 01_PROJECT_OVERVIEW.md
    └── logs/
```

## Architecture | 架构

### Files Installed | 安装的文件

| Path | Purpose | 用途 |
|------|---------|------|
| `~/.claude/radioheader/INDEX.md` | Master index of all topic files | 主题文件主索引 |
| `~/.claude/radioheader/project-registry.md` | Registry of all projects (name, stack, path) | 项目注册表 |
| `~/.claude/radioheader/topics/*.md` | Experience files by technology/domain | 按技术领域组织的经验文件 |
| `~/.claude/radioheader/shortwave/*.md` | Refined, project-agnostic knowledge entries | 精炼的项目无关知识条目 |
| `~/.claude/hooks/radioheader-loader.sh` | SessionStart: shows RadioHeader status | 显示就绪状态 |
| `~/.claude/hooks/check-project-architecture.sh` | SessionStart: detects unconfigured projects | 检测未配置项目 |
| `~/.claude/hooks/radioheader-memory-sync.sh` | PostToolUse: triggers reflux on memory/ writes | memory 写入时触发回流 |
| `~/.claude/hooks/radioheader-stop-reflux.sh` | Stop: reflux checklist reminder | 会话结束回流提醒 |
| `~/.claude/CLAUDE.md` | RadioHeader rules between markers | 规则追加在标记之间 |
| `~/.claude/radioheader/templates/project/` | Project init templates | 项目初始化模板 |
| `/usr/local/bin/radioheader` (or `~/bin/`) | CLI tool | CLI 工具 |

### How Experience Flows | 经验流转

```
You solve a bug in Project A          在项目 A 中修复 bug
        │
        ▼
Claude records it in Project A's memory/
        │
        ▼
PostToolUse hook fires → reflux check  PostToolUse hook 触发 → 回流检查
        │
        ▼
Claude checks: Is this useful cross-project?
        │  Yes
        ▼
Writes to ~/.claude/radioheader/topics/{topic}.md
  with [source:ProjectA] tag
        │
        ▼
PostToolUse hook fires → shortwave refinement trigger
        │
        ▼
Claude distills → writes to shortwave/sw-{domain}-{N}.md
  (project-agnostic, searchable)
        │
        ▼
Later, in Project B, you hit a similar issue
        │
        ▼
Claude searches RadioHeader → shortwave first, then topics
        │
        ▼
Cites it: "RadioHeader has experience from ProjectA: ..."
        │
        ▼
Applies the solution (or verifies applicability first)
```

## Lessons Learned | 实战经验

RadioHeader was built through real-world usage across 13 projects. Key insights:

> RadioHeader 在 13 个项目的实际使用中打磨而成。

1. **"Searched but didn't use" is the #1 failure mode.** Early versions told Claude to search RadioHeader, but the agent would search, find results, and then completely ignore them. The fix: make the behavioral rule three mandatory steps (Search → Apply → Trace) with an explicit prohibition on finding but not using.

   > **"搜到但没用"是头号失败模式。** 修复：三步强制规则（搜→用→追）+ 禁止搜到不用。

2. **Symptom keywords matter more than solution keywords.** Developers search by symptoms ("white screen", "slow launch") not by solutions ("Task.detached"). Strip the symptoms and the entry becomes unfindable.

   > **症状关键词比解决方案关键词更重要。** 开发者搜"白屏"不搜"Task.detached"。

3. **Instructions beat knowledge.** Writing "experience is stored in RadioHeader" (informational) doesn't drive behavior. Writing "you MUST search RadioHeader first" (imperative) does. CLAUDE.md content must be behavioral instructions, not reference documentation.

   > **指令胜过知识。** "这里有经验"不够，"你必须先搜"才能驱动行为。

4. **Bidirectional flow is essential.** One-way aggregation (project → global) creates a stale knowledge base. The reflux cycle (project → global → project) keeps experience alive and verified.

   > **双向流转至关重要。** 单向聚合会过时，回流循环保持鲜活。

5. **PostToolUse `additionalContext` is the strongest behavioral driver.** Injecting system-level context via hook JSON output is more reliable than CLAUDE.md rules alone for triggering specific actions at the right moment.

   > **PostToolUse `additionalContext` 是最强行为驱动。** 通过 hook JSON 输出注入系统级上下文，比单靠 CLAUDE.md 规则更可靠。

## Docs | 文档

- [How It Works | 工作原理](docs/how-it-works.md) — Architecture and behavioral design
- [Shortwave Spec | 短波规范](docs/shortwave-spec.md) — Shortwave format, refinement rules, pseudonymization
- [Writing Good Entries | 编写指南](docs/writing-good-entries.md) — Format, keywords, and examples
- [Lessons Learned | 经验教训](docs/lessons-learned.md) — What we tried, what failed, what works

## License

MIT
