# Multi-Machine Sync — 集成规格

> 把「两台机器双向自动同步 RadioHeader 知识库 + 项目记忆」从一次性搭建沉淀为 `radioheader sync` 内建功能的完整规格。
> 本文基于 2026-07-16/17 在两台 Mac(MBP16 `Zaptain` / MBP14 `zaptain`)上跑通并验证的原型。原型工作文件见文末「参考实现」。

## 实现状态(2026-07-17,v2.3.0)

**Phase A + B + C(配对与向导)均已实现**(`radioheader device-sync`)。

Phase C(普通用户 onboarding,超出本 spec 原始范围):`setup` 交互向导(首台:gh 一键建仓或浏览器引导 → init → 可选 encrypt → 配对;接入:自动发现 iCloud 配对包 / ~/Downloads 的 AirDrop 配对文件 / 手动兜底,join 失败按认证指引重试)。配对双通道:**AirDrop**(明文 `.rhpair` 含 URL+密钥,一次性,提示双侧删除)与 **iCloud + 口令**(密钥经 AES-256+PBKDF2 口令加密后放 `iCloud Drive/RadioHeader/`,join 成功即焚;口令不落盘不上云——iCloud 只见「口令加密的密钥」,GitHub 只见「密钥加密的记忆」,单一云端凑不齐两半)。注:iCloud 钥匙串的可同步条目无法从 `security` CLI 写入(需 kSecAttrSynchronizable),口令加密包是与用户确认过的等价替代。join 的 clone 失败现在区分认证失败(gh auth login / ssh-keygen+pbcopy+open 配方)、仓库不存在、其它。

**Phase C 抓到的严重坑(已修)**:无钥机器 join 加密 vault 时,若 meta 重写只看本机 flag(false),会把 `project-memories/` 重新写进 .gitignore 并 **untrack vault 里全部加密记忆再推送**——污染所有机器。修:meta 写入以「本机 flag **或** vault HEAD 的 .gitattributes 已含 filter 行」为准(`_sync_pm_meta_on`),e2e 加了「keyless join 后 vault 记忆仍在」回归断言。

Phase B 新增:

- **加密项目记忆通道**(§3b):`encrypt` / `key export|import` / `join --key`;四重安全闸(opt-in 标志 + git-crypt 在场 + 已解锁 + filter 行在 .gitattributes),任一不满足则该通道静默关闭、知识库照常同步。
- **防错钥闸**:vault 已有密文而本机未解锁时 `encrypt` 拒绝生成新钥(会永久解不开旧密文),指引 `key import`;`join --key` 在临时 clone 中 unlock(工作区必干净),密钥与 filter 配置随 `.git/` 收养移入。
- **删除语义(墓碑)**——解决原型「rsync 无 --delete → 删除复活」缺口:机器本地 `.sync-pm-seen` 记录上次 distribute 清单;本地删除 → staging 移除 + 写 `<file>.tombstone`(内容=epoch);其它机器 distribute 时按「本地 mtime > 墓碑时间则文件获胜(重建),否则删本地」执行;墓碑 90 天 GC。独立小文件避开「密文不能 union」的共享清单冲突。
- doctor 密文验真(`git cat-file blob` 绕过 filter,校验 GITCRYPT 魔数,发现明文即红色告警+轮换指引);Codex `hooks.json` 同步注册/注销;README 双语章节。
- 踩坑补充:staging 相对路径以 `-HOME-` 开头,`dirname`/`basename` 会当成选项报 `illegal option`——hook 内一律用参数展开(`${rel%/*}` / `${rel##*/}`)。

与本 spec 的其余偏差(Phase A 起,均有意为之,理由见 planning log `2026-07-17-device-sync-v2-phaseA-plan-cc.md`):

- **CLI 表面是 `radioheader device-sync`,不是 §7 的 `sync`**——顶层 `sync` 已被社区库同步命令占用;v1 `device-sync` 本就是同一需求的手动版,原地升级为 v2(init/join/now/status/off,旧 push/pull/clone 保留为别名)。
- **知识库明文同步默认开启;项目记忆加密同步 opt-in**(`encrypt` 显式启用,未启用时 `.gitignore` 排除 `project-memories/`)。原型的两个缺口已在 Phase B 解决:① 删除复活 → 墓碑机制(见上);② 密钥丢失 → export 默认落仓库外 + 每个入口(encrypt/export/join --key)都强提示离线备份。
- **config.json / templates/ 不同步**(修正 §2 的跟踪清单):config.json 含 per-machine 设置(`device_sync_enabled` 等),templates/ 由 install.sh 管理。
- **config 键为扁平的 `device_sync_enabled`**,不是 §7 的嵌套 `sync{}`(CLI 的 config_get 是扁平 grep 解析)。
- **hook 脚本内嵌在 CLI 中**由 `device-sync init` 写入 `~/.claude/hooks/radioheader-git-sync.sh`(单一来源,老安装只升级 CLI 也自足),默认不注册、init/join 时才写入 settings.json(deny-by-default)。
- **冲突可见性增强**:merge 失败(以 MERGE_HEAD 区分真冲突与离线)落 `.sync-diverged` 标记,`status` / `doctor` 检测并给出解决指引——解决「真冲突静默永久推迟」问题。
- e2e 测试:`tests/test_device_sync.sh`(多假 HOME + file:// bare 仓库,52 项断言:init/join/union 收敛/排除项/v1 升级 untrack/锁/off/加密验真/跨用户名分发/墓碑传播/重建获胜/无钥防泄漏;git-crypt 缺失时加密段自动跳过)。

---

## 1. 目标与选型

**目标**:多台机器上的 `~/.claude/radioheader/`(知识库)+ `~/.claude/projects/*/memory/`(项目记忆)双向、自动、可合并地同步;不丢经验、机密不明文上云、不要求各机用户名一致。

**选型对比**(都要先排除 SQLite 索引):

| 方案 | 自动 | 双向 | 真合并 | 机密安全 | 云依赖 | 结论 |
|------|:--:|:--:|:--:|:--:|:--:|------|
| iCloud/Dropbox | ✅ | ✅ | ❌(冲突副本 `x 2`) | ❌ | ✅ | SQLite 易损坏、无合并、污染索引 |
| Syncthing | ✅ | ✅ | ❌(`.sync-conflict`) | ⚠️ | ❌ | 按块同步、天生不能内容合并 |
| **git 旁挂层** | 靠 hook | ✅ | ✅(union) | ✅(git-crypt) | 私有仓库/自建 | **采用** |

**核心洞见**:git 是唯一能"真合并"的;它唯一缺的"自动"用 hook 补上(会话开始 pull、结束 push)。做成**不改 RadioHeader 本体的可逆 sidecar**——目录里叠个 `.git/`,本体黑盒无感。

---

## 2. 同步范围(关键:只同步可移植内容,派生/机器本地一律本地重建)

`.gitignore`(排除项,各机 `radioheader consolidate` / `index` 本地重建):
```
search.db  search.db-wal  search.db-shm  search.db-journal   # SQLite 索引:损坏风险,绝不同步
context-digest.md  project-registry.md                        # consolidate 派生
project-registry.json                                         # ⚠️ consolidate 按各机注意力权重重排 → 同步会反复冲突,本地生成
community/                                                     # 独立 git 仓库(社区源),各机自拉
error-log.jsonl  search-log.jsonl  pending-votes.jsonl  pending-publish/   # 机器本地日志/瞬时态
.consolidate-counter  .radiomind-suggested                    # 机器本地状态计数
.DS_Store
```

跟踪(同步)项:`topics/ shortwave/ templates/ user-profile.md INDEX.md config.json project-memories/`(项目记忆 staging)。

**为什么排除 `project-registry.json`**(踩坑得来):它被 consolidate 按各机使用习惯重排,两台顺序不同 → 每次同步 modify/delete 或内容冲突 → `merge --abort` 阻断**整轮**同步。权重本就该反映各机使用,故本地生成。

---

## 3. 两层数据模型

### 3a. 知识库(明文 + union 真合并)
不含机密,直接 git 跟踪。`.gitattributes` 给**追加型文件**设 `merge=union` → 两机并发追加自动并入双方,不冲突不丢:
```
shortwave/*.md    merge=union
topics/*.md       merge=union
community/**/*.md merge=union
INDEX.md          merge=union
user-profile.md   merge=union
# project-registry.json 不设 union(JSON 合并会破坏结构)——但它已被 .gitignore 排除
```

### 3b. 项目记忆(git-crypt 加密 + 用户名归一)
`~/.claude/projects/*/memory/` **含真实机密**(实盘 TOTP、VPS root、路由器密码)。**绝不明文进 git**,哪怕私有仓库(云端副本 + 永久历史 + deploy key 泄露面)。

- **git-crypt** 只加密项目记忆子目录:`.gitattributes` 加 `project-memories/** filter=git-crypt diff=git-crypt`(知识库仍明文可 union)。工作区/本机明文,git blob / GitHub 密文。
- **对称密钥**:`git-crypt init` 生成,存 `.git/git-crypt/keys/default`(148 字节,不进版本控制)。经 **SSH/带外**传给其它机器 `git-crypt unlock`,**绝不经 GitHub**。
- **密钥须离线备份**(如密码管理器):丢了则 GitHub 上密文永久解不开。`git-crypt export-key <file>`。
- **验证加密真生效**:`git cat-file blob HEAD:<file>` 应为 `GITCRYPT` 密文头,明文 canary 命中=0。

**路径归一**(不要求各机用户名一致):`~/.claude/projects/` 下编码目录名形如 `-Users-<user>-Library-...`,两机仅 `<user>` 段不同(`Zaptain`/`zaptain`)。
- 编码→归一:`sed 's/^-Users-[^-]*-/-HOME-/'`(staging 里存 `-HOME-...`)
- 归一→本机:`sed "s/^-HOME-/-Users-$(whoami)-/"`

---

## 4. reconcile 算法(单一操作,双向对等,绝不丢)

```
reconcile():
  1. collect_pm    本机各项目 memory/*.md → staging/-HOME-<key>/(归一;rsync 不 --delete,防丢/误删)
                   [安全闸:git-crypt 未解锁则跳过项目记忆,绝不明文入库]
  2. git add -A;  有变化才 commit(git-crypt 自动加密 project-memories/**)
  3. git pull --no-rebase --no-edit --autostash   合并远端(知识库 union;密文项目记忆常规合并)
        失败(真冲突)→ git merge --abort  保留本地提交、推迟(绝不丢)
  4. git push      离线则推迟,下次再推
  5. distribute_pm staging/-HOME-<key>/ → 本机 -Users-<me>-<key>/memory/(反归一;缺失则创建,开项目时已就位)
  6. 若 HEAD 变化 → radioheader index  增量重建 FTS 索引
```

**为什么 collect 在 pull 之前**:先把本机改动落地到 staging,再让 git pull 用 union 合并,distribute 写回合并结果——保证本地改动不被覆盖、双方都在。

---

## 5. 自动化(绑 Claude 会话生命周期,非 launchd 看门狗)

hook(`settings.json`):
- `SessionStart` → `radioheader-git-sync.sh pull`(**后台化**:`nohup "$0" &` 重执行自身,hook 瞬间返回、不拖慢启动 ~5s 网络往返;digest 已由 loader 本地同步加载)
- `Stop` → `radioheader-git-sync.sh push`(前台;有本地新经验才提交推送)

并发保护:`mkdir` 原子锁 + **>3min 陈旧锁自清**(防某次被杀留死锁永久禁用同步)。

---

## 6. 关键踩坑(不修则同步静默失效)

1. **`git pull` 分叉报 `fatal: Need to specify how to reconcile divergent branches`**:未配策略时 git 拒绝合并,reconcile 一遇分叉就 `merge --abort` 永不收敛。迷惑点:手动 `git merge origin/main` 却能成。**修**:`git config pull.rebase false` + 脚本 `git pull --no-rebase`。
2. **`project-registry.json` 每机重排 → 每轮冲突阻断**:排除出 git,本地生成(见 §2)。
3. **`community/` 是嵌入 git 仓库**:`git add` 会当 gitlink(`warning: adding embedded git repository`),必须 `.gitignore` 排除。
4. **git-crypt 加密文件无法 union/行合并**:并发改同一密文文件会真冲突。项目记忆通常单机轮流编辑,罕见;`merge --abort` 保留本地推迟即可,不丢。
5. **加密安全闸**:git-crypt 未解锁(无 `keys/default`)时**绝不** collect/distribute 项目记忆,否则明文入库。
6. **首次分叉 bootstrap**:两台初次都各有 auto-sync 提交时会分叉,一次手动 merge 收敛后即稳。

---

## 7. 集成为 `radioheader sync` 的建议

### CLI 表面
```
radioheader sync init [--remote <url>] [--encrypt]     # 本机:git init + .gitignore/.gitattributes + git-crypt init + 关联远端 + 首推 + 装 hook
radioheader sync join <url> [--key <keyfile>]          # 新机:clone + 装 CLI/hook + git-crypt unlock + consolidate + distribute
radioheader sync now                                    # 手动跑一次 reconcile
radioheader sync status                                 # 分支/收敛/待推/加密解锁状态
radioheader sync key export <file> / import <file>      # git-crypt 密钥导出/导入
radioheader sync off                                    # 卸载 hook + 保留仓库(可逆)
```

### config.json 新增键
```json
{
  "sync": {
    "enabled": true,
    "remote": "git@github.com:<user>/radioheader-vault.git",
    "encrypt_project_memories": true,      // git-crypt 开关
    "sync_project_memories": true,         // 是否纳入 project-memories
    "pull_on_session_start": true,
    "push_on_stop": true
  }
}
```

### 门槛评估(做成通用功能)
- **能全自动化**(一条命令):git init、.gitignore/.gitattributes、git-crypt init、装 hook(用系统原生 launchd `WatchPaths` 免 fswatch 依赖)、`consolidate`、第二机 `join`。
- **唯一硬门槛**:用户自备**私有 git 远端 + 凭据**(开发者低;非技术用户高。工具替不了第三方账号)。
- **真正难点**:冲突不卡死(union + `--no-rebase` + `merge --abort` 保留双方)、加密密钥的带外分发与备份提醒。
- 建议:默认关闭、opt-in;远端支持私有 GitHub(deploy key 单仓库最小权限)或自建 VPS bare repo(不落第三方)。

---

## 8. 参考实现(原型已验证)

原型工作文件(可直接抄进 install.sh / 打包进工具):
- **同步脚本**:`~/.claude/hooks/radioheader-git-sync.sh`(collect/distribute/reconcile 全逻辑,~90 行 bash)
- **`.gitignore` / `.gitattributes`**:见 §2 / §3
- **依赖**:`git`、`git-crypt`(brew)、`rsync`、`python3`(FTS5 走 python 的 sqlite3 模块,无需 sqlite3 CLI);macOS CLT 自带 python3
- **第二机落地步骤**(供 `sync join` 参照):
  1. `ssh-keygen` → `gh repo deploy-key add --allow-write`(或加账号 SSH key)
  2. `git clone`(443 端口 SSH 防火墙友好)vault → `~/.claude/radioheader`;`git config core.sshCommand` 固定用该 key;`git config pull.rebase false`
  3. 拷 CLI `~/bin/radioheader` + `fts-index.py/fts-search.py/attn-consolidate.py`;`~/bin` 入 PATH
  4. `git-crypt unlock <经 SSH 传来的密钥>`;`radioheader index --rebuild` + `radioheader consolidate`
  5. 拷 `radioheader-*` hook 脚本;`settings.json` 加 SessionStart(git-sync pull + loader)/PostToolUse/Stop(stop-echo + git-sync push)

### 验证记录(2026-07-17)
- 知识库:两台各改同文件制造分叉 → 各自 reconcile 后都收敛,union 合并含双方标记(不丢)
- 项目记忆:16 个两台明文可用,GitHub blob 密文(TOTP 明文命中=0),更新亦正确传播解密
- 分叉:`--no-rebase` 后自动收敛,不再报 divergent

> 实测部署环境细节见 Homeclash 项目 `logs/2026-07-16-radioheader-multi-machine-git-sync-cc.md`。
