#!/usr/bin/env python3
"""Manage only RadioHeader's Kimi hooks; preserve other TOML bytes and secrets."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile

try:
    import tomllib
except ImportError:
    raise SystemExit('Kimi configuration requires Python 3.11+ (tomllib); config was not changed.')

START = '# --- RadioHeader Kimi START ---'
END = '# --- RadioHeader Kimi END ---'
EVENTS = ('SessionStart', 'UserPromptSubmit', 'Stop', 'SessionEnd', 'PostToolUseFailure')


def config_path():
    return Path(os.environ.get('KIMI_CODE_HOME') or Path.home() / '.kimi-code') / 'config.toml'


def expected_hooks():
    script = Path.home() / '.claude/hooks/radioheader-kimi.py'
    return [dict(event=event, **({'matcher': '^Bash$'} if event == 'PostToolUseFailure' else {}), command=shlex.quote(sys.executable) + ' ' + shlex.quote(str(script)) + ' ' + event,
                 timeout=120 if event in ('Stop', 'SessionEnd') else 30) for event in EVENTS]


def strip_managed(raw):
    # Refuse ambiguous/truncated ownership markers rather than dropping config.
    if raw.count(START) != raw.count(END) or raw.count(START) > 1:
        raise ValueError('Unbalanced RadioHeader Kimi markers; restore config before retrying.')
    if START in raw:
        raw = re.sub(r'(?m)^' + re.escape(START) + r'\n.*?^' + re.escape(END) + r'\n?', '', raw, flags=re.S)
    return raw


def owned(hook):
    try:
        args = shlex.split(hook.get('command', ''))
    except ValueError:
        return False
    return len(args) == 3 and Path(args[1]) == Path.home() / '.claude/hooks/radioheader-kimi.py' and args[2] in EVENTS


def without_owned(data):
    result = dict(data)
    hooks = [hook for hook in result.pop('hooks', []) if not owned(hook)]
    if hooks:
        result['hooks'] = hooks
    return result


def update(path, remove=False, dry_run=False):
    raw = path.read_text() if path.exists() else ''
    data = tomllib.loads(raw)
    base = strip_managed(raw)
    # Kimi may reserialize TOML and discard comments. Remove only exact adapter
    # command entries in that case, retaining unrelated tables byte-for-byte.
    chunks = re.split(r'(?m)(?=^\[\[hooks\]\]\s*(?:#.*)?$)', base)
    kept = []
    for chunk in chunks:
        if chunk.startswith('[[hooks]]'):
            boundary = re.search(r'(?m)^\[(?!\[hooks\]\])', chunk[len('[[hooks]]'):])
            end = len('[[hooks]]') + boundary.start() if boundary else len(chunk)
            block = chunk[:end]
            hook = tomllib.loads(block).get('hooks', [{}])[0]
            if owned(hook):
                chunk = chunk[end:]
        kept.append(chunk)
    base = ''.join(kept)
    if not remove:
        # Inline top-level hooks cannot be extended with [[hooks]] safely.
        parsed = tomllib.loads(base)
        if 'hooks' in parsed and not re.search(r'(?m)^\[\[hooks\]\]', base):
            raise ValueError('Inline hooks are unsupported; convert hooks to [[hooks]] tables first.')
        blocks = [START]
        for hook in expected_hooks():
            blocks += ['[[hooks]]'] + [key + ' = ' + json.dumps(value, ensure_ascii=False) for key, value in hook.items()]
        base = base.rstrip() + '\n\n' + '\n'.join(blocks) + '\n' + END + '\n'
    result = tomllib.loads(base)
    if without_owned(result) != without_owned(data):
        raise ValueError('Cannot safely preserve custom TOML structure; config was not changed.')
    managed = [hook for hook in result.get('hooks', []) if owned(hook)]
    if managed != ([] if remove else expected_hooks()):
        raise ValueError('Cannot safely replace managed hooks; config was not changed.')
    if dry_run or raw == base:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + '.radioheader.bak.' + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'))
        backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(backup_fd, 'w') as stream:
            stream.write(raw)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.radioheader-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(base)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def check(path):
    data = tomllib.loads(path.read_text())
    hooks = data.get('hooks', [])
    missing = [h['event'] for h in expected_hooks() if h not in hooks]
    script = Path.home() / '.claude/hooks/radioheader-kimi.py'
    agents = path.parent / 'AGENTS.md'
    for name in ('radioheader-kimi.py', 'radioheader-codex-userprompt.py', 'radioheader-stop-codex.py'):
        if not (script.parent / name).is_file(): missing.append(name)
    if not agents.exists() or 'RadioHeader START' not in agents.read_text(): missing.append('AGENTS.md rules')
    if missing:
        raise ValueError('Kimi missing/mismatched: ' + ', '.join(missing))
    print('Kimi config, managed hooks and AGENTS.md OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['install', 'remove', 'check', 'validate'])
    parser.add_argument('--config', type=Path, default=config_path())
    args = parser.parse_args()
    try:
        if args.action == 'check': check(args.config)
        elif args.action == 'remove' and not args.config.exists(): pass
        else: update(args.config, args.action == 'remove', args.action == 'validate')
    except (OSError, ValueError) as exc:
        # TOML exceptions contain location, not the full config or credentials.
        raise SystemExit('Kimi configuration error: ' + str(exc))
