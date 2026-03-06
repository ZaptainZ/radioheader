# RadioHeader

**让 Claude Code 拥有跨项目记忆。** 在项目 A 踩过的坑，项目 B 不必再踩。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[English](README.md)

## 问题

Claude Code 的记忆是按项目隔离的。你在一个 app 里修了 SwiftUI NavigationStack 的 bug，三个月后在另一个 app 中遇到同样的问题——Claude 从零开始分析。所有已解决的问题都被锁死在当初的项目里。

RadioHeader 在所有项目之间建立共享经验中枢，Claude 在分析技术问题之前**必须先搜索这里**。

## 装了之后有什么不同

**没装 RadioHeader** — 项目 B 遇到白屏问题：

```
你：App 启动白屏 10 秒以上

Claude：让我查查……[读文件、跑调试器、查日志]
        ……30 分钟后……
        找到了！.onAppear 里的 Task {} 继承了 MainActor，
        iCloud I/O 阻塞主线程。
        修复：用 Task.detached(priority:)
```

**装了 RadioHeader** — 同样的问题：

```
你：App 启动白屏 10 秒以上

Claude：RadioHeader 中有来自 ProjectA 的经验：
        "SwiftUI .onAppear 中的 Task {} 继承 Main Actor，
        iCloud I/O 阻塞主线程，导致 10s+ 白屏。
        修复：用 Task.detached(priority:)"

        验证一下是否适用于当前项目…… ✓ 同样的模式。
        正在应用修复。
```

10 秒搞定，省了 30 分钟——因为经验已经存在了。

## 核心特性

**跨项目记忆** — 三层模型：RadioHeader（全局共享）→ 项目 memory/（项目专属）→ 会话上下文（临时）。经验从项目流向全局中枢，再流回到需要它的地方。

**搜 → 用 → 追** — 不是建议，是注入 CLAUDE.md 的强制行为规则。搜到相关经验就**必须引用并应用**，搜到不用是被明确禁止的。

**自动经验回流** — 四个 hooks 驱动完整闭环：SessionStart 显示状态、PostToolUse 检测 memory 写入并触发回流、Stop 提醒检查新经验。不需要手动操作。

**知识短波（Shortwave）** — Topic 条目含项目细节（`[source:MyApp]`）。短波去掉这些细节，提炼为通用的、项目无关的知识单元——跨技术栈可搜索。

## 快速开始

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh
```

搞定。启动 Claude Code 进入任何项目，RadioHeader 即刻生效——hooks 自动触发、规则自动加载、经验随时可搜。

可选：在某个项目中运行 `radioheader init` 可添加项目级脚手架（回流规则、日志目录、文档模板）。这不是必需的——RadioHeader 无需此步即可全局工作。

## 工作原理

```
RadioHeader (~/.claude/radioheader/)
├── shortwave/   ← 精炼的、项目无关的知识
├── topics/      ← 带 [source:] 标签的详细经验
└── INDEX.md     ← 主索引

    ▲ 回流  ║ 搜索
    ║       ▼

项目 A memory/     项目 B memory/     项目 N memory/
```

修 bug 时，Claude 先记录到项目的 memory/ 中。PostToolUse hook 触发后，Claude 判断：*这条经验跨项目有用吗？* 如果是，写入 `topics/` 并标注 `[source:项目名]`，然后精炼为 `shortwave/` 条目。

之后在另一个项目中遇到类似问题，**搜→用→追** 规则启动：先搜 RadioHeader，引用并应用搜到的经验，需要更多细节时追溯到源项目。

## 使用技巧

**主动触发回流。** Hooks 会自动处理大部分回流，但你也可以随时用自然语言告诉 Claude：

- *"同步项目信息"* — Claude 更新项目概述文档并检查全局回流
- *"把今天的经验更新一下"* — Claude 回顾学到的内容，写入 memory/topics
- *"写个今天的日志"* — Claude 在日志目录创建任务日志

适合在长会话结束前、完成一个功能后、或觉得最近的工作应该被记录时使用。

## CLI 命令

| 命令 | 功能 |
|------|------|
| `radioheader init` | 在项目中初始化经验框架 |
| `radioheader search <关键词>` | 搜索所有 topics 和 shortwave |
| `radioheader status` | 查看主题数、条目数、注册项目 |
| `radioheader doctor` | 健康检查：hooks、规则、注册表 |
| `radioheader align` | 分析 topics↔shortwave 覆盖率 |
| `radioheader align --execute` | 输出批量精炼指令供 Claude 执行 |
| `radioheader align --refs` | 校验并修复 shortwave 引用链接 |

```bash
# 按症状搜索，不是按解法搜索
radioheader search "白屏|启动慢|startup"

# 用参数模式初始化项目
radioheader init --name "MyAPI" --stack "Python/FastAPI" --doc-dir docs
```

## 实战经验

在 13 个项目中实际使用，打磨出的三条关键教训：

**"搜到但没用"是头号失败模式。** 早期版本告诉 Claude 要搜 RadioHeader，它确实搜了，也确实找到了结果——然后完全忽略。修复方法：把行为规则升级为三个强制步骤（搜→用→追），并明确禁止搜到不用。行为指令胜过知识描述。

**症状关键词 > 解法关键词。** 开发者搜的是"白屏"、"启动慢"，不是"Task.detached"。经验条目如果删掉了症状词，就再也搜不到了。每条经验必须保留用户实际会搜索的词。

**指令胜过知识。** 写"经验存在这里"不会驱动行为，写"你必须先搜这里"才会。CLAUDE.md 的内容必须是强制性行为指令，不是参考文档。

更多详见 [docs/lessons-learned.md](docs/lessons-learned.md)。

## 文档

| 文档 | 内容 |
|------|------|
| [工作原理](docs/how-it-works.md) | 架构和行为设计 |
| [短波规范](docs/shortwave-spec.md) | Shortwave 格式和精炼规则 |
| [编写指南](docs/writing-good-entries.md) | 格式、关键词和示例 |
| [经验教训](docs/lessons-learned.md) | 试过什么、什么失败了、什么有效 |
| [示例 Topics](examples/topics/) | Topic 文件示例 |

## License

MIT
