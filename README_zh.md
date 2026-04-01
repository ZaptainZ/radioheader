# RadioHeader

**让 Claude Code 拥有跨项目记忆。** 在项目 A 踩过的坑，项目 B 不必再踩。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[English](README.md)

## 问题

像 Claude Code 这样的编程 Agent，分析问题很强，但不会积累经验。即便有了原生的 memory 系统，也只记得大致方向，记不住关键细节。而且项目之间的记忆完全隔离——项目 A 踩过的坑，项目 B 根本不知道。

现有工具（`.cursorrules`、`awesome-rules`、CLAUDE.md）都在做"规则"层面的事。RadioHeader 做的是**经验**层面——那些得自己撞上、解决了才真正印象深刻的认知型知识。

名字的由来——我喜欢 Radiohead 这个乐队，而这个全局中枢又像一个信号塔，各个项目需要的时候就从里面接收信息。RadioHeader，就这么来的。

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

同一类问题从第二次开始，解决时间从分钟级掉到秒级。不是 AI 变聪明了，是答案已经在那里了。

## 核心特性

**三层记忆模型** — RadioHeader（全局共享）→ 项目 memory/（项目专属）→ 会话上下文（临时）。经验从项目流向全局中枢，再流回到需要它的地方。

**Echo（经验回流）** — 完成任务后，经验自动流回记忆系统。四个 hooks 驱动完整闭环：SessionStart 显示状态、PostToolUse 检测 memory 写入并触发 Echo、Stop 提醒检查新经验。不需要手动操作。

**Shortwave（知识短波）** — Topic 条目含项目细节（`[source:MyApp]`）。短波去掉项目名、文件路径、框架细节，提炼为通用的、项目无关的知识单元——跨技术栈可搜索。这也是在保护隐私：原始条目可能包含项目路径、内部命名甚至 API key，短波会把这些全部剥离。

**搜 → 用 → 追** — 不是建议，是注入 CLAUDE.md 的强制行为规则。搜到相关经验就**必须引用并应用**，搜到不用是被明确禁止的。

**Learn（外部知识采集）** — RadioHeader 不只靠踩坑积累经验。`learn` 命令从任意 URL 提取文章——包括微信公众号、Medium、Substack 等封闭平台——并提炼为短波条目。这让 RadioHeader 从被动的经验管理器升级为 Claude Code 的主动**信息入口**：不只记住教训，而是主动从外部世界吸收知识。

**环境认知摘要（注意力压缩）** — 灵感来自 [Kimi 的 Attention Residuals](https://github.com/MoonshotAI/Attention-Residuals) 研究。RadioHeader 构建一份压缩的环境认知画像，在每次会话开始时注入。注意力机制不作用于搜索排序（内容匹配已经足够好），而是作用于**记忆整合**层面——类似人类睡眠中的记忆巩固。每隔几次记忆同步，`consolidate` 自动运行，生成 `context-digest.md`，包含：用户特征（解题风格、长处、已知短板）、带 **scope 标注**的项目全景（每个项目的路径，Agent 可直接导航）、近期搜索热点、跨项目技术交叉。摘要强制执行 **3,500 字符预算**（参考 Claude Code 内部 4K/文件的指令截断阈值）——项目增多时，低优先级 section 自动裁剪，loader hook 层还有二次兜底保护。Agent 每次会话一开始就知道自己在帮谁——不只是在看什么代码。

**用户画像（三个维度）** — RadioHeader 跨三个维度维护用户模型：(1) **做过什么**——项目组合，每个项目的领域、问题和痛点，记录在 `project-registry.json`；(2) **怎么工作**——解题方式、交互偏好、已知长处和短板；(3) **有什么资源**——设备、网络环境、基础设施。这份画像是记忆整合的"查询向量"——决定了什么被强调、什么被关联、Agent 应该主动关注什么。

**社区共享** — 可选的社区短波库。你的本地经验始终留在本地；发布时经过三关检查（质量评分 ≥6/8、隐私扫描、去重检查）才能进入共享池。质量治理采用 [Stigmergy（痕迹协作）](https://zh.wikipedia.org/wiki/%E5%8D%8F%E4%BD%9C%E6%80%A7) 模型——类似蚁群信息素：好条目通过使用被强化，差条目自然衰减。

## 快速开始

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh
```

搞定。启动 Claude Code 进入任何项目，RadioHeader 即刻生效——hooks 自动触发、规则自动加载、经验随时可搜。安装器具有容错能力：如果现有 `settings.json` 已损坏，会自动备份并重建，不会报错退出。

可选：在某个项目中运行 `radioheader init` 可添加项目级脚手架（Echo 规则、日志目录、文档模板）。这不是必需的——RadioHeader 无需此步即可全局工作。

## 工作原理

```
RadioHeader (~/.claude/radioheader/)
├── shortwave/            ← 精炼的、项目无关的知识
├── topics/               ← 带 [source:] 标签的详细经验
├── project-registry.json ← 项目名片（领域、问题、痛点）
├── user-profile.md       ← 用户画像（工作方式、资源）
├── context-digest.md     ← 环境认知摘要（自动生成）
└── INDEX.md              ← 主索引

    ▲ Echo        ║ 搜索      consolidate ──→ context-digest.md
    ║             ▼                                    ║
                                                       ▼
项目 A memory/       项目 B memory/       SessionStart（自动注入）
```

修 bug 时，Claude 先记录到项目的 memory/ 中。PostToolUse hook 触发后，Claude 判断：*这条经验跨项目有用吗？* 如果是，写入 `topics/` 并标注 `[source:项目名]`，然后精炼为 `shortwave/` 条目。

三层这样接上：经验先通过 **Echo** 回到 **RadioHeader**，再由 **Shortwave** 去掉项目噪音，变成可广播的通用知识。

之后在另一个项目中遇到类似问题，**搜→用→追** 规则启动：先搜 RadioHeader，引用并应用搜到的经验，需要更多细节时追溯到源项目。

### Learn — 第二条知识通道

Echo 从踩坑中捕获经验。`learn` 从文章中捕获知识：

```
信息源                      RadioHeader               消费端
─────────────────           ─────────────────         ─────────────────
踩坑修复 (Echo) ─────────→                        ──→ search 命令
外部文章 (learn) ────────→  topics/ + shortwave/  ──→ Agent 搜→用→追
社区共享 (sync) ─────────→                        ──→ publish 投稿
用户行为 ────────────────→  consolidate           ──→ context-digest（SessionStart 注入）
```

这让 RadioHeader 成为一个**信息入口**——外部知识流入 Claude Code 工作记忆的统一入口。不是浏览器，不是书签管理器，而是一个能吸收、提炼、并在需要时精准供给知识的系统。

### Consolidate — 睡眠中的记忆整合

人类的记忆在睡眠中压缩：具体事件渐渐模糊，但规律和技能沉淀下来。RadioHeader 的 `consolidate` 做同样的事：

```
记忆同步不断积累 → 每 5 次自动触发 consolidate
                              ↓
              分析搜索日志 + 项目活跃度 + 用户画像
                              ↓
              生成 context-digest.md（压缩的环境认知）
                              ↓
              下次会话：Agent 一开始就拥有完整的环境上下文
```

环境认知摘要在读任何代码之前就告诉 Agent：
- **在帮谁**——解题风格、长处、已知短板
- **他在做什么**——12 个项目的领域、痛点、活跃度
- **最近在关注什么**——搜索热词和焦点领域
- **哪些技术跨越了多个项目**——技能迁移的机会在哪里

这不是搜索优化——是 **Agent 校准**。区别在于：没有摘要时，Agent 对每个用户一视同仁。有了摘要，Agent 知道这个用户倾向于在启动路径上做贪婪加载、schema 迁移测试不充分、最近在关注搜索质量优化。这些上下文影响 Agent 的每一条建议。

### 社区共享

默认社区仓库是 [radioheader-community](https://github.com/ZaptainZ/radioheader-community)（可通过 `config.json` 指向自己的仓库）。

开启社区后（`radioheader community on`），搜索结果同时包含本地和社区条目：

```
📡 Shortwave (本地精炼)  — 你自己的经验（最高优先级）
🌐 Community (社区共享)  — 其他用户的条目，附带质量分数
📂 Topics (详细)         — 你的原始 topic 条目
```

质量治理采用 [Stigmergy（痕迹协作）](https://zh.wikipedia.org/wiki/%E5%8D%8F%E4%BD%9C%E6%80%A7) 模型——类似蚁群信息素：
- 新条目有 30 天曝光期
- 使用时自动投票（LLM 判断因果贡献）
- 投票每周通过 GitHub Actions 聚合为分数
- 高分条目标记 `verified`，低分条目衰减并归档

发布需过三关：质量（≥6/8）、隐私扫描（无路径/密钥/来源标签）、去重检查。

## 使用技巧

**主动触发 Echo。** Hooks 会自动处理大部分回流，但你也可以随时用自然语言告诉 Claude：

- *"同步项目信息"* — Claude 更新项目概述文档并检查全局 Echo
- *"把今天的经验更新一下"* — Claude 回顾学到的内容，写入 memory/topics
- *"写个今天的日志"* — Claude 在日志目录创建任务日志

适合在长会话结束前、完成一个功能后、或觉得最近的工作应该被记录时使用。

## CLI 命令

| 命令 | 功能 |
|------|------|
| `radioheader init` | 在项目中初始化经验框架 |
| `radioheader search <关键词>` | 搜索 topics、shortwave 和社区库 |
| `radioheader index [--rebuild]` | 构建/更新 FTS5 搜索索引（BM25 + 同义词） |
| `radioheader learn <url>` | 提取网页文章并生成短波条目 |
| `radioheader consolidate` | 更新项目权重并生成环境认知摘要 |
| `radioheader upgrade` | 将已注册项目升级到最新模板 |
| `radioheader status` | 查看主题数、条目数、社区状态 |
| `radioheader doctor` | 健康检查：hooks、规则、注册表 |
| `radioheader align` | 分析 topics↔shortwave 覆盖率 |
| `radioheader align --execute` | 输出批量精炼指令供 Claude 执行 |
| `radioheader align --refs` | 校验并修复 shortwave 引用链接 |
| `radioheader community on\|off\|status` | 社区共享开关 |
| `radioheader sync` | 同步社区库 + 上传投票/条目 |
| `radioheader publish <文件>` | 发布短波到社区（三关检查） |
| `radioheader publish --auto-detect` | 扫描本地可发布的短波 |
| `radioheader vote <id> [+1\|-1]` | 投票评价短波条目 |
| `radioheader device-sync init <url>` | 跨设备同步初始化（via git） |
| `radioheader device-sync push\|pull` | 在设备间推送/拉取 RadioHeader 数据 |

```bash
# 按症状搜索，不是按解法搜索
radioheader search "白屏|启动慢|startup"

# 用参数模式初始化项目
radioheader init --name "MyAPI" --stack "Python/FastAPI" --doc-dir docs

# 开启社区并同步
radioheader community on
radioheader sync
```

## 实战经验

在 13 个项目中实际使用，打磨出的三条关键教训：

**"搜到但没用"是头号失败模式。** 早期版本告诉 Claude 要搜 RadioHeader，它确实搜了，也确实找到了结果——然后完全忽略。修复方法：把行为规则升级为三个强制步骤（搜→用→追），并明确禁止搜到不用。行为指令胜过知识描述。

**症状关键词 > 解法关键词。** 开发者搜的是"白屏"、"启动慢"，不是"Task.detached"。经验条目如果删掉了症状词，就再也搜不到了。每条经验必须保留用户实际会搜索的词。

**指令胜过知识。** 写"经验存在这里"不会驱动行为，写"你必须先搜这里"才会。CLAUDE.md 的内容必须是强制性行为指令，不是参考文档。

**注意力属于记忆压缩，不属于搜索。** 我们最初把注意力权重加到搜索结果上（提升活跃项目的条目排名）。测试发现排序变化为零——BM25 内容匹配已经给出了正确结果。注意力真正的价值在于记忆整合：将用户的项目全景、行为模式和已知短板压缩成一份摘要，影响的是 Agent 怎么思考，而不是搜到什么。

更多详见 [docs/lessons-learned.md](docs/lessons-learned.md)。

## 文档

| 文档 | 内容 |
|------|------|
| [工作原理](docs/how-it-works.md) | 架构和行为设计 |
| [质量标准](docs/quality-standards.md) | 评分规则和审计清单 |
| [短波规范](docs/shortwave-spec.md) | Shortwave 格式和精炼规则 |
| [编写指南](docs/writing-good-entries.md) | 格式、关键词和示例 |
| [经验教训](docs/lessons-learned.md) | 试过什么、什么失败了、什么有效 |
| [示例 Topics](examples/topics/) | Topic 文件示例 |

## License

MIT
