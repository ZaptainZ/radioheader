# RadioHeader

**编程 Agent 的跨项目记忆——在项目 A 踩过的坑，项目 B 不必再踩。**

```
你：App 启动白屏 10 秒以上

Claude：RadioHeader 中有来自 ProjectA 的经验：
        "SwiftUI .onAppear 中的 Task {} 继承 Main Actor，
        iCloud I/O 阻塞主线程，导致 10s+ 白屏。
        修复：用 Task.detached(priority:)"

        验证一下是否适用…… ✓ 同样的模式。正在修复。
```

一次安装，Claude Code、Codex CLI 和所有 MCP 兼容 Agent 通用，共享同一份记忆。

[English](README.md) · [工作原理](docs/how-it-works.md) · [MCP 服务](docs/mcp-server.md) · [实战经验](docs/lessons-learned.md)

---

## 它做什么

编程 Agent 分析问题很强，但不会积累经验。即便有了原生 memory 系统，项目之间的记忆完全隔离——项目 A 踩过的坑，项目 B 根本不知道。

RadioHeader 用三个机制解决这个问题：

| 机制 | 做什么 |
|------|--------|
| **Echo（回波）** | 任务完成后，经验通过 hooks 自动从项目流回全局记忆中枢 |
| **搜 → 用 → 追** | 注入 `CLAUDE.md` / `AGENTS.md` 的检索指引：按症状判断是否值得搜索，核验命中是否适用，引用后应用，必要时追溯来源 |
| **Shortwave（短波）** | 从经验条目中剥离项目名、文件路径、框架细节，产出跨技术栈可搜索的通用知识单元 |

效果：任何项目的任何 Agent 第二次碰到同类问题时，答案已经在那里了。

## RadioHeader 给编程 Agent 带来了什么

| 能力 | 没有 RadioHeader | 有 RadioHeader |
|------|-----------------|---------------|
| **跨项目经验** | 每个项目是孤岛 | 12+ 项目的经验流向需要它的地方 |
| **复用相关记忆** | 过去的经验容易被遗漏 | 搜→用→追：核验适用性、引用来源、应用相关经验 |
| **从文章学习** | 复制粘贴到 prompt | `radioheader learn <url>` 自动提取、精炼为可搜索条目 |
| **Agent 校准** | Agent 对每个用户一视同仁 | 环境认知摘要：知道你的项目全景、长处、已知短板 |
| **社区知识** | 从零开始 | 可选的共享库，Stigmergy 信息素质量治理 |

---

## 记忆如何流动

```
对话（bug 修复、功能开发、调试会话）
     │
     ▼
 ┌─ Echo（自动，通过 hooks）──────────────────────┐
 │  Claude：PostToolUse Write|Edit → 即时触发       │
 │  Codex： UserPromptSubmit 快照 + Stop diff       │
 │  结果：经验写入项目 memory/                       │
 └───────────────────────────┬───────────────────────┘
                             ▼
 ┌─ 三层记忆 ────────────────────────────────────┐
 │                                                │
 │  项目 memory/ ──── 跨项目有用？──→              │
 │                       是 ↓                     │
 │  RadioHeader topics/ ── [source:项目名] ──→     │
 │                       提炼 ↓                   │
 │  RadioHeader shortwave/ ── 项目无关 ──→         │
 │                       全局可搜索                │
 └───────────────────────────┬───────────────────┘
                             ▼
 ┌─ 搜 → 用 → 追 ───────────────────────────────┐
 │  下次任何 Agent 碰到类似问题：                   │
 │  1. 搜：radioheader search "<症状>"             │
 │       (FTS5 + 中英同义词扩展)                   │
 │  2. 用：在回复中引用命中条目                     │
 │  3. 追：沿 [source:] 追溯到来源项目              │
 └──────────────────────────────────────────────┘
```

```
RadioHeader (~/.claude/radioheader/)
├── shortwave/            ← 精炼的、项目无关的知识
├── topics/               ← 带 [source:] 标签的详细经验
├── project-registry.json ← 项目名片（领域、问题、痛点）
├── context-digest.md     ← 环境认知摘要（自动生成）
└── INDEX.md              ← 主索引
```

<details>
<summary><b>Consolidate — 记忆在睡眠中巩固</b></summary>

人类的记忆在睡眠中压缩：情节淡去，模式固化。RadioHeader 的 `consolidate` 做同样的事：

```
记忆同步累积 → CC 每 5 次写入 / Codex 每 5 个有变化的回合自动 consolidate
                        ↓
        分析搜索日志 + 项目活跃度 + 用户画像
                        ↓
        生成 context-digest.md（压缩的环境认知）
                        ↓
        下次会话：Agent 开局就知道在帮谁
```

摘要在任何代码被读取之前告诉 Agent：解题风格、项目全景、近期关注、技术交叉、已知短板。不是搜索优化——是 **Agent 校准**。

本地后台刷新由默认开启的 `auto_digest` 控制。RadioMind 后台调用需显式设置 `radiomind_auto: true` 或 `RADIOHEADER_RADIOMIND_AUTO=1`；环境变量 `0` 可明确关闭。前台 `consolidate` 可委托 RadioMind，`consolidate --native` 始终只做本地处理。`search_hits` 表示最近 30 天命中数，每次重算，避免重复累计。

</details>

<details>
<summary><b>社区共享 — Stigmergy 信息素模型</b></summary>

可选的社区库（[radioheader-community](https://github.com/ZaptainZ/radioheader-community)）。质量治理采用 [Stigmergy](https://zh.wikipedia.org/wiki/%E5%8D%8F%E4%BD%9C%E6%80%A7) 模型——类似蚁群信息素：

- 新条目获得 30 天曝光期
- 使用触发自动投票（LLM 评判因果贡献）
- 投票每周通过 GitHub Actions 汇总为分数
- 高分条目标记 `verified`，低分条目自然衰减并归档

发布需过三关：质量（≥6/8）、隐私扫描、去重检查。

```
📡 Shortwave（本地精炼）  — 你自己的经验（最高优先级）
🌐 Community（社区共享）  — 来自其他用户的条目，带质量分
📂 Topics（详细）         — 带 [source:] 标签的原始条目
```

</details>

<details>
<summary><b>MCP 服务 — 供 Cursor、Claude Desktop 等使用</b></summary>

RadioHeader 内置可选的 MCP 服务（8 个只读工具），任何 [MCP](https://modelcontextprotocol.io/) 兼容 Agent 都可以查询同一份经验层：

```bash
pip install "mcp[cli]"
radioheader mcp-server          # 启动 stdio 服务
```

工具：`radioheader_search`、`radioheader_list_projects`、`radioheader_trace_project`、`radioheader_read_shortwave`、`radioheader_read_topic`、`radioheader_list_topics`、`radioheader_context_digest`、`radioheader_stats`。

详见 [docs/mcp-server.md](docs/mcp-server.md)。

> 如果你使用 [RadioMind](https://github.com/ZaptainZ/radiomind)，它的 MCP 服务已包含 RadioHeader 搜索，无需同时配置两个。

</details>

---

## 双 Runtime 支持

RadioHeader 的数据层只有一份，上层通过**运行时适配器**对接不同的编程 Agent：

| | Claude Code | Codex CLI | MCP 客户端 |
|---|---|---|---|
| 入口文件 | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` | System prompt |
| Echo 触发 | `PostToolUse Write\|Edit` | `UserPromptSubmit` 快照 + `Stop` diff | — |
| 项目脚手架 | `.claude/settings.json` | `.codex/hooks.json` | — |

Codex 侧采用**快照 + 差分**闭环（涵盖 `apply_patch` 和 shell 写入）：`UserPromptSubmit` 在每个 turn 前对 memory/topics/shortwave 做指纹；`Stop` 时 diff，发现 Echo 链有缺位就用 `decision: block` + continuation prompt 补齐。

首次使用仍需遵循客户端权限流程：Codex 的新增或变更 Hook 要先通过 `/hooks` 审阅；CC 写入 `~/.claude/` 下的全局 topics/shortwave 时，即使处于 `acceptEdits`，也可能要求确认，普通 settings allow 规则不能预先批准受保护路径写入。请在正常权限提示中批准具体编辑；无法取得批准的无界面 `-p` 会话可能无法完成 Echo 链。参见 [Codex Hook 信任](https://learn.chatgpt.com/docs/hooks) 和 [CC 受保护路径](https://code.claude.com/docs/en/permission-modes#protected-paths)。

Python hooks 目标 **Python 3.7+**（`from __future__ import annotations`）。仓库遍历上限 10k 文件，24 小时 TTL 自动清理陈旧快照。

---

## 安装

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh --runtime both
```

搞定。启动 Claude Code 或 Codex 进入任何项目——hooks 自动触发、规则自动加载、经验随时可搜。

```bash
./install.sh --runtime claude   # 只装 Claude Code
./install.sh --runtime codex    # 只装 Codex CLI
./install.sh --runtime both     # 默认
```

可选：在项目中运行 `radioheader init` 添加项目级脚手架（Echo 规则、日志目录、文档模板）。

## 维护

无人值守重装到用户目录（保留既有社区开关）：

```bash
./install.sh --runtime both --yes --bin-dir "$HOME/bin"
radioheader doctor
radioheader index --rebuild  # 按需重建派生索引
radioheader consolidate --native
```

2.4.1 新增 Codex 每 5 个记忆变化回合自动刷新本地摘要；重装时刷新设备同步脚本，保留同步开关。修复增量 FTS 一致性、本地/社区 ID 冲突、注册表备份恢复、Codex 记忆路径与后台门控、模板个人路径。`doctor` 用只读快照核验 FTS，有问题时返回非零退出码。

回归测试：`python3 -m unittest discover -s tests -p 'test_maintenance.py'`、`python3 tests/test_digest_quality.py`、`bash tests/test_auto_digest.sh`、`bash tests/test_device_sync.sh`。

## 使用

```bash
# 按症状搜索，不是按解法搜索
radioheader search "白屏|启动慢|startup"

# 初始化项目
radioheader init --name "MyAPI" --stack "Python/FastAPI"

# 从文章学习
radioheader learn https://example.com/article

# 健康检查
radioheader doctor
```

**全部命令：**

| 命令 | 功能 |
|------|------|
| `search <关键词>` | BM25 + 同义词搜索 topics、shortwave、社区库 |
| `init` | 项目脚手架（`--runtime claude\|codex\|both`） |
| `index [--rebuild]` | 构建/更新 FTS5 搜索索引 |
| `learn <url>` | 提取文章为短波条目 |
| `consolidate` | 更新注意力权重和环境认知摘要 |
| `upgrade` | 将已注册项目升级到最新模板 |
| `status` | 主题数、短波数、社区状态 |
| `doctor` | 健康检查：hooks、规则、注册表、RadioMind |
| `align` | topics↔shortwave 覆盖率分析 |
| `community on\|off` | 社区共享开关 |
| `sync` | 同步社区库 + 上传投票 |
| `publish <文件>` | 发布短波到社区（三关检查） |
| `vote <id> [+1\|-1]` | 投票评价短波条目 |
| `device-sync` | 多机同步（git 旁挂 + 自动 hook，可选 git-crypt 加密） |
| `mcp-server` | 启动 MCP 服务（stdio），供 Cursor / Claude Desktop 使用 |

---

## 多机同步

让几台 Mac 共用同一份知识库。`device-sync` 在 `~/.claude/radioheader/` 上叠一个
git「旁挂」仓库，随 Claude 会话自动收敛：会话开始后台 pull、会话结束 push。

最简单的方式——两台 Mac 各跑一次向导，按提示回答即可：

```bash
radioheader device-sync setup
```

向导会帮你创建私有 GitHub 仓库（有 `gh` 时一键建仓），然后引导另一台 Mac 接入：
**在身边** → AirDrop 一个一次性配对文件；**不在身边** → 口令加密的配对包走
iCloud Drive（口令装在你脑子里，不经过任何云端）。

device-sync 的全部提示与消息均为中英双语——根据系统 locale（`LANG`/`LC_ALL`）
自动选中文，也可用 `RADIOHEADER_LANG=zh|en` 强制指定（或在
`~/.claude/radioheader/config.json` 里设置 `"language"` 键）。

手动等价命令：

```bash
# 机器 A —— 指向一个你自己的【私有】仓库
radioheader device-sync init --remote git@github.com:you/radioheader-vault.git

# 机器 B —— 本地已有数据不会丢：与 vault 自动合并
radioheader device-sync join git@github.com:you/radioheader-vault.git
```

追加型文件（`topics/`、`shortwave/`、`INDEX.md`）用 git union 合并——两台机器同时
改同一个文件，双方内容都保留。真实冲突会保留双方提交历史：同步自动推迟，
`device-sync status` / `doctor` 会告诉你如何解决。收到变更后刷新搜索索引；digest 与 registry.md 是机器本地派生视图。**`project-registry.json` 是机器本地真源**：同步前保存有效的 `.project-registry.backup.json`。native consolidate 可从备份恢复；真源与备份均不可用时明确报错，不会以空表覆盖项目名片。会话快照也不参与同步。

**项目记忆**（`~/.claude/projects/*/memory/`）可能含真实机密，只以加密形式同步——
需显式开启：

```bash
radioheader device-sync encrypt                    # 机器 A：git-crypt 初始化
radioheader device-sync key export                 # 密钥务必离线备份
radioheader device-sync join <url> --key <密钥文件> # 机器 B（密钥走 SSH/AirDrop）
```

本机明文、vault 密文（`doctor` 会验证已提交 blob 的密文魔数）。密钥绝不经过
vault 传递；删除通过墓碑标记跨机传播，删除后重建的文件获胜。随时可用
`radioheader device-sync off` 关闭（仓库保留，可逆）。

---

## RadioMind 集成

[RadioMind](https://github.com/ZaptainZ/radiomind) 是 AI Agent 的仿生记忆核心——它通过三体辩论和做梦修剪把零散对话提炼为深层习惯，在需要的时候把它们送回来。RadioHeader 负责捕获和行为强制，RadioMind 负责精炼和深化。

前台命令会检测 PATH 中的 RadioMind；后台自动调用须另外显式开启：

| 命令 | 没有 RadioMind | 有 RadioMind |
|------|--------------|-------------|
| `radioheader search` | FTS5 + 同义词扩展 | 金字塔检索 + 知识图谱 + 习惯匹配 |
| `radioheader consolidate` | 注意力权重 + context digest | Dream 精炼（SHY 修剪 + DMN 漫游）+ 更丰富的 digest |

RadioMind 直接读取 RadioHeader 的 `topics/` 和 `shortwave/` 文件。RadioHeader 不需要知道 RadioMind 存在——它只是检测 PATH 上有没有 `radiomind`，有就委托，没有就走原生路径。

```
RadioHeader（捕获 + 规则）              RadioMind（精炼 + 增强）
────────────────────                  ────────────────────
Echo hooks → 写 topics/shortwave/ ──→ adapter 读取、索引、精炼
radioheader search ── radiomind? 是 ─→ radiomind rh-search
                  └── 否 ─→ fts-search.py（原生）
radioheader consolidate ─ radiomind? → radiomind rh-consolidate
                        └── 否 ─→ attn-consolidate.py（原生）
```

## 社区库

[radioheader-community](https://github.com/ZaptainZ/radioheader-community) 是一个可选的社区共享短波库。你的本地经验始终留在本地；你选择发布的条目需过三关才能进入共享池。

```bash
radioheader community on          # 启用
radioheader sync                  # 拉取共享库 + 上传投票
radioheader publish <文件>         # 发布（质量 ≥6/8 + 隐私 + 去重）
```

质量治理采用 [Stigmergy（信息素）](https://zh.wikipedia.org/wiki/%E5%8D%8F%E4%BD%9C%E6%80%A7) 模型——类似蚁群：好条目通过使用被强化，差条目自然衰减，不需要人工管理。

| 阶段 | 发生什么 |
|------|---------|
| **曝光** | 新条目获得 30 天曝光窗口 |
| **投票** | 使用触发自动 LLM 评判（因果贡献投票） |
| **汇总** | GitHub Actions 每周汇总投票为质量分 |
| **生命周期** | 高分条目标记 `verified`；低分条目衰减并归档 |

启用后，搜索结果混合三个来源并有明确优先级：

```
📡 Shortwave（本地精炼）  — 你自己的经验（最高优先级）
🌐 Community（社区共享）  — 来自其他用户的条目，带质量分
📂 Topics（详细）         — 带 [source:] 标签的原始条目
```

---

## 实战经验

跨 13 个项目的真实使用总结出的四条经验：

**"搜到但没用"——头号失败模式。** Claude 搜到了结果，但完全跳过不用。早期通过三步强制规则改善；当前模板已调整为按症状判断检索价值，应用时核验适用性并引用来源。

**症状关键词 > 解法关键词。** 开发者搜的是"白屏"、"启动慢"，不是"Task.detached"。每条经验必须保留用户实际会搜索的词。

**指令胜过知识。** 写"经验存在这里"不会驱动行为，明确何时搜索、怎样核验命中、到哪里记录新经验，才能让知识库发挥作用。

**注意力属于记忆压缩，不属于搜索。** 注意力加权排序变化为零——BM25 已经给出了正确结果。注意力真正的价值在于记忆整合：把用户的项目全景压缩成 Agent 的思维底色。

详见 [docs/lessons-learned.md](docs/lessons-learned.md)。

---

## Radio 生态

| 项目 | 做什么 | 和 RadioHeader 的关系 | 阶段 |
|------|--------|---------------------|------|
| **RadioHeader** | 编程 Agent 跨项目经验框架。捕获调试经验并强制复用。 | 本仓库。"规则与捕获"层。 | 已发布，240+ 条经验 |
| **[RadioMind](https://github.com/ZaptainZ/radiomind)** | 仿生记忆核心。把对话提炼为习惯（三体辩论 + 做梦修剪）。 | 读取 RadioHeader 数据并增强。RadioHeader 检测到 RadioMind 后自动升级 search/consolidate。 | 已发布 |
| **RadioHand** | 个人 Agent 框架。多通道、任务规划、工具调度。 | 将使用 RadioMind 做记忆，RadioHeader 做经验规则。 | 规划中 |

```
RadioHeader（规则与经验）→ RadioMind（记忆与习惯）→ RadioHand（执行与通道）
         头                        脑                        手
```

## 文档

| 文档 | 内容 |
|------|------|
| [工作原理](docs/how-it-works.md) | 架构与行为设计 |
| [MCP 服务](docs/mcp-server.md) | Cursor、Claude Desktop 等配置指南 |
| [短波规范](docs/shortwave-spec.md) | Shortwave 格式与精炼规则 |
| [质量标准](docs/quality-standards.md) | 评分标准与审计清单 |
| [写好条目](docs/writing-good-entries.md) | 格式、关键词与示例 |
| [实战经验](docs/lessons-learned.md) | 踩过的坑、试过的方案、有效的做法 |

## 许可

MIT
