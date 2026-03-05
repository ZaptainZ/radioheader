# RadioHeader

**Claude Code 跨项目经验共享框架。**

RadioHeader 为 Claude Code 提供跨项目的持久记忆层。在项目 A 中解决的棘手 bug，其经验会自动在项目 B、C 以及所有未来项目中可用。

## 问题

Claude Code 的记忆是按项目隔离的。你在一个 app 中修复了 SwiftUI NavigationStack 的 bug，三个月后在另一个 app 中遇到同样的问题——Claude 又从零开始分析。

RadioHeader 通过创建一个共享经验中枢来解决这个问题，Claude 在分析任何技术问题之前会先搜索这里。

## 工作原理

```
┌─────────────────────────────────────────────────┐
│                  RadioHeader                     │
│          ~/.claude/radioheader/topics/            │
│                                                  │
│  ios-swiftui.md  ·  rust-systems.md  ·  ...     │
│  [source:AppA] NavigationStack 嵌套 bug...       │
│  [source:AppB] Swift 并发陷阱...                  │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┼────────────────┐
        ▼            ▼                ▼
   ┌─────────┐ ┌─────────┐     ┌─────────┐
   │ 项目 A  │ │ 项目 B  │     │ 项目 N  │
   │ memory/ │ │ memory/ │     │ memory/ │
   └─────────┘ └─────────┘     └─────────┘
```

**三层记忆模型：**

1. **RadioHeader**（全局）— 跨项目经验，所有项目共享
2. **项目记忆**（`~/.claude/projects/*/memory/`）— 项目特定上下文
3. **会话上下文** — 临时的，仅在单次对话中存在

**行为规则 — 搜→用→追：**

1. **搜**：遇到技术问题时，Claude 必须先搜索 RadioHeader
2. **用**：如果找到相关经验，Claude 必须引用并应用
3. **追**：如果需要更多细节，Claude 追溯到源项目的 memory/ 目录

这不是可选的——RadioHeader 会在 Claude 的 CLAUDE.md 中注入强制性行为规则，所以 Agent **必须**搜索、应用、追溯。找到经验但不使用是被明确禁止的。

## 安装

### 前置条件

- 已安装 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)（`~/.claude/` 目录存在）
- 推荐安装 `jq` 用于自动合并 settings.json（`brew install jq` / `apt install jq`）

### 安装

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh
```

安装器会：
- 创建 `~/.claude/radioheader/` 及索引和注册文件
- 安装两个会话 hook 到 `~/.claude/hooks/`
- 将 RadioHeader 行为规则追加到 `~/.claude/CLAUDE.md`
- 将 hook 合并到 `~/.claude/settings.json`
- 为所有修改的文件创建带时间戳的备份

### 卸载

```bash
cd radioheader
./uninstall.sh
```

卸载器会移除所有 RadioHeader 组件。如果你有经验文件，会在删除前询问确认。

## 使用

### 自动模式（正常工作即可）

安装后，RadioHeader 自动工作：

1. **会话开始**：hook 触发，显示"RadioHeader ready (N topic files)"
2. **新项目检测**：如果项目未配置，Claude 会询问是否启用动态经验框架
3. **问题解决**：遇到技术问题时，Claude 先搜索 RadioHeader 再开始分析
4. **经验回流**：完成一个任务系列后，Claude 检查是否有新经验需要回流到 RadioHeader

### 编写经验条目

经验在工作过程中自然积累。条目写入 `~/.claude/radioheader/topics/` 下的主题文件，格式如下：

```markdown
- [source:MyApp] SwiftUI `.onAppear` 中的 `Task {}` 继承 Main Actor —
  iCloud I/O 阻塞主线程，导致 10s+ 白屏（首次加载慢 / 启动延迟）。
  修复：使用 `Task.detached(priority:)`
```

**关键原则：**

- 保留**症状关键词**（"白屏"、"加载慢"、"10s+"）— 用户按症状搜索
- 包含**量化数据**（"20-40s" 而不只是"慢"）
- 添加**同义词**（括号内注明，提高搜索命中率）
- 标注**源项目** `[source:Name]` 用于追溯
- 一条经验一行 — 简洁但完整

参见 [`examples/topics/`](examples/topics/) 获取完整示例。

### 项目级配置

安装 RadioHeader 后首次打开项目时，Claude 会提供启用动态经验框架的选项。启用后创建：

```
your-project/
├── .claude/
│   ├── settings.json         # 项目级 hooks
│   ├── hooks/
│   │   └── load-project-rules.sh
│   └── rules/
│       ├── memory-reflux.md  # 经验回流规则
│       ├── logs-writing.md   # 日志写入规则
│       └── information-lookup.md  # 信息查找策略
├── CLAUDE.md                 # 项目入口
└── {文档目录}/
    ├── 00_AGENT_RULES.md
    ├── 01_PROJECT_OVERVIEW.md
    └── logs/
```

## 架构

### 安装的文件

| 路径 | 用途 |
|------|------|
| `~/.claude/radioheader/INDEX.md` | 所有主题文件的主索引 |
| `~/.claude/radioheader/project-registry.md` | 项目注册表（名称、技术栈、路径） |
| `~/.claude/radioheader/topics/*.md` | 按技术/领域组织的经验文件 |
| `~/.claude/hooks/radioheader-loader.sh` | 会话 hook：显示 RadioHeader 状态 |
| `~/.claude/hooks/check-project-architecture.sh` | 会话 hook：检测未配置的项目 |
| `~/.claude/CLAUDE.md` | RadioHeader 规则追加在标记之间 |

### 经验流转

```
你在项目 A 中修复了一个 bug
        │
        ▼
Claude 记录到项目 A 的 memory/ 中
        │
        ▼
Claude 检查：这个经验跨项目有用吗？
        │  是
        ▼
写入 ~/.claude/radioheader/topics/{topic}.md
  带 [source:ProjectA] 标签
        │
        ▼
之后，在项目 B 中你遇到类似问题
        │
        ▼
Claude 搜索 RadioHeader → 找到条目
        │
        ▼
引用："RadioHeader 有来自 ProjectA 的经验：..."
        │
        ▼
应用解决方案（或先验证适用性）
```

## 实战经验

RadioHeader 在 13 个项目的实际使用中打磨而成。关键洞察：

1. **"搜到但没用"是头号失败模式。** 早期版本告诉 Claude 搜索 RadioHeader，但 Agent 会搜索、找到结果，然后完全忽略。修复方法：将行为规则改为三个强制步骤（搜→用→追），并明确禁止找到但不使用。

2. **症状关键词比解决方案关键词更重要。** 开发者按症状搜索（"白屏"、"加载慢"）而不是按解决方案（"Task.detached"）。去掉症状关键词，条目就搜不到了。

3. **指令胜过知识。** 写"经验存储在 RadioHeader 中"（信息性描述）不能驱动行为。写"你必须先搜索 RadioHeader"（指令性描述）才能驱动行为。CLAUDE.md 的内容必须是行为指令，不是参考文档。

4. **双向流转至关重要。** 单向聚合（项目→全局）会创建一个过时的知识库。回流循环（项目→全局→项目）让经验保持鲜活和经过验证。

## 文档

- [工作原理](docs/how-it-works.md) — 架构和行为设计
- [编写好的条目](docs/writing-good-entries.md) — 格式、关键词和示例
- [经验教训](docs/lessons-learned.md) — 我们尝试了什么、什么失败了、什么有效

## 许可证

MIT
