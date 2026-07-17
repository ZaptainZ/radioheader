#!/bin/bash
# RadioHeader git-sync (旁挂层) —— 会话开始/结束各跑一次统一 reconcile,双向、永不阻塞、绝不丢。
# 同步两类:
#   ① radioheader 知识库(git 直接跟踪,明文,union 真合并)——无机密
#   ② 各项目 ~/.claude/projects/*/memory/(经 staging + 用户名归一 + git-crypt 加密)
#      GitHub 上是密文,仅本机/工作区明文;两台各存对称密钥(经 SSH 传递,不经 GitHub)
#   pull : 后台 reconcile(hook 瞬间返回,不拖慢会话启动)
#   push : 前台 reconcile
# 依赖:git、git-crypt、rsync、~/bin/radioheader。仓库缺失/未解锁/离线都安全跳过(exit 0)。
set +e
RH="$HOME/.claude/radioheader"
[ -d "$RH/.git" ] || exit 0
PROJECTS="$HOME/.claude/projects"
PM="$RH/project-memories"            # 项目记忆 staging(git-crypt 加密后随 vault 同步)

MODE="${1:-pull}"

# pull 默认后台化:重执行自身脱离 hook 生命周期,主调用瞬间返回
if [ "$MODE" = "pull" ] && [ "${RH_SYNC_BG:-}" != "1" ]; then
  RH_SYNC_BG=1 nohup "$0" pull >/dev/null 2>&1 &
  exit 0
fi

cd "$RH" || exit 0

# 安全闸:git-crypt 未解锁则绝不碰项目记忆(避免明文入库)。只同步知识库。
CRYPT_OK=0
if command -v git-crypt >/dev/null 2>&1 && [ -f "$RH/.git/git-crypt/keys/default" ]; then
  CRYPT_OK=1
fi

# 防并发 + 陈旧锁自清(>3min)
LOCK="$RH/.sync.lock"
[ -d "$LOCK" ] && [ -n "$(find "$LOCK" -maxdepth 0 -mmin +3 2>/dev/null)" ] && rmdir "$LOCK" 2>/dev/null
if ! mkdir "$LOCK" 2>/dev/null; then exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s 2>/dev/null || echo mac)"
ME="$(whoami)"

# 收集:本机各项目 memory/ → staging(归一化去用户名前缀;不 --delete,防丢/误删)
collect_pm() {
  [ "$CRYPT_OK" = 1 ] || return
  for md in "$PROJECTS"/-Users-*/memory; do
    [ -d "$md" ] || continue
    ls "$md"/*.md >/dev/null 2>&1 || continue
    local enc key
    enc="$(basename "$(dirname "$md")")"
    key="$(printf '%s' "$enc" | sed 's/^-Users-[^-]*-/-HOME-/')"
    mkdir -p "$PM/$key"
    rsync -a --include='*.md' --exclude='*' "$md/" "$PM/$key/" 2>/dev/null
  done
}

# 分发:staging → 本机各项目 memory/(反归一化换本机用户名;缺失则创建,开项目时已就位)
distribute_pm() {
  [ "$CRYPT_OK" = 1 ] || return
  [ -d "$PM" ] || return
  for kd in "$PM"/-HOME-*; do
    [ -d "$kd" ] || continue
    local key enc dest
    key="$(basename "$kd")"
    enc="$(printf '%s' "$key" | sed "s/^-HOME-/-Users-$ME-/")"
    dest="$PROJECTS/$enc/memory"
    mkdir -p "$dest"
    rsync -a --include='*.md' --exclude='*' "$kd/" "$dest/" 2>/dev/null
  done
}

reconcile() {
  collect_pm                                   # 1. 本机记忆 → staging(合并前先落地,防被覆盖)
  git add -A 2>/dev/null                        # 2. 提交本地全部变化(知识库明文 + staging 由 git-crypt 加密)
  git diff --cached --quiet 2>/dev/null || git commit -q -m "auto-sync: $HOST $(date +%Y-%m-%dT%H:%M)" 2>/dev/null
  local before after
  before="$(git rev-parse HEAD 2>/dev/null)"
  if ! git pull --no-rebase --no-edit --autostash --quiet 2>/dev/null; then   # 3. 合并远端(--no-rebase 显式 merge 策略,分叉不再拒绝;知识库 union,密文项目记忆常规合并)
    git merge --abort 2>/dev/null              #    真冲突:保留本地提交,推迟(绝不丢)
  fi
  after="$(git rev-parse HEAD 2>/dev/null)"
  git push --quiet 2>/dev/null || true          # 4. 推送(离线则推迟)
  distribute_pm                                 # 5. 合并结果 → 本机各项目 memory/
  [ "$before" != "$after" ] && "$HOME/bin/radioheader" index >/dev/null 2>&1   # 6. 变化才重建索引
}

reconcile
exit 0
