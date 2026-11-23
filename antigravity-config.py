#!/usr/bin/env python3
"""Manage only RadioHeader's Antigravity CLI hooks in ~/.gemini/config/hooks.json.

hooks.json is an object of named hooks; RadioHeader owns exactly the
top-level "radioheader" entry. Every other named hook is preserved; the
result is verified before an atomic replace with a private backup.
"""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

NAME = 'radioheader'
SCRIPT_NAME = 'radioheader-antigravity.py'
# Lifecycle events take handlers directly; tool events take matcher groups.
# Antigravity timeouts are in seconds.
LIFECYCLE = {'SessionStart': 30, 'PreInvocation': 15, 'Stop': 120}
TOOL = {'PostToolUse': ('run_command', 15)}


def gemini_dir():
    return Path.home() / '.gemini'


def script_path():
    return Path.home() / '.claude/hooks' / SCRIPT_NAME


def command(event):
    return shlex.quote(sys.executable) + ' ' + shlex.quote(str(script_path())) + ' ' + event


def expected_entry():
    entry = {}
    for event, timeout in LIFECYCLE.items():
        entry[event] = [{'type': 'command', 'command': command(event), 'timeout': timeout}]
    for event, (matcher, timeout) in TOOL.items():
        entry[event] = [{'matcher': matcher, 'hooks': [{'type': 'command', 'command': command(event), 'timeout': timeout}]}]
    return entry


def load(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text())  # comments/trailing commas are refused
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError('hooks.json must be an object of named hook objects')
    return data


def owned_commands(entry):
    commands = []
    for event, items in (entry or {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for handler in item.get('hooks', [item]):
                if isinstance(handler, dict) and handler.get('command'):
                    commands.append(handler['command'])
    return commands


def is_ours(entry):
    """Only replace an existing "radioheader" entry that RadioHeader wrote."""
    commands = owned_commands(entry)
    for cmd in commands:
        try:
            args = shlex.split(cmd)
        except ValueError:
            return False
        if len(args) != 3 or Path(args[1]).name != SCRIPT_NAME:
            return False
    return bool(commands)


def update(path, remove=False, dry_run=False):
    raw = path.read_text() if path.exists() else None
    data = load(path)
    if NAME in data and not is_ours(data[NAME]):
        raise ValueError('hooks.json already has a "radioheader" hook not written by RadioHeader; not changed.')
    result = copy.deepcopy(data)
    result.pop(NAME, None)
    if not remove:
        result[NAME] = expected_entry()
        # A user who toggled RadioHeader off in /hooks keeps that choice.
        if 'enabled' in data.get(NAME, {}):
            result[NAME] = dict(enabled=data[NAME]['enabled'], **result[NAME])
    others = {k: v for k, v in result.items() if k != NAME}
    if others != {k: v for k, v in data.items() if k != NAME}:
        raise ValueError('Cannot safely preserve other hooks; hooks.json was not changed.')
    if dry_run or result == data or (raw is None and remove):
        return
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = 0o600
    if raw is not None:
        mode = path.stat().st_mode & 0o777
        backup = path.with_name(path.name + '.radioheader.bak.' + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'))
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(raw)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.radioheader-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def normalize(value, problems):
    """Compare hook commands by script + event; the recorded interpreter may
    legitimately differ from the one running this check, but must still exist."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == 'command' and isinstance(item, str):
                try:
                    args = shlex.split(item)
                except ValueError:
                    args = []
                if len(args) == 3 and Path(args[1]).name == SCRIPT_NAME:
                    if not os.access(args[0], os.X_OK):
                        problems.append('hook interpreter missing: ' + args[0])
                    item = args[1] + ' ' + args[2]
            out[key] = normalize(item, problems)
        return out
    if isinstance(value, list):
        return [normalize(item, problems) for item in value]
    return value


def check(path):
    data = load(path)
    problems = []
    entry = data.get(NAME)
    if entry is None:
        problems.append('radioheader hook entry')
    else:
        if entry.get('enabled') is False:
            problems.append('radioheader hooks disabled ("enabled": false)')
        if normalize({k: v for k, v in entry.items() if k != 'enabled'}, problems) != normalize(expected_entry(), []):
            problems.append('radioheader hook entry mismatched')
    hooks_dir = script_path().parent
    for name in (SCRIPT_NAME, 'radioheader-codex-userprompt.py', 'radioheader-stop-codex.py'):
        if not (hooks_dir / name).is_file():
            problems.append(name)
    rules = gemini_dir() / 'GEMINI.md'
    if not rules.exists() or 'RadioHeader START' not in rules.read_text():
        problems.append('~/.gemini/GEMINI.md rules')
    if problems:
        raise ValueError('Antigravity missing/mismatched: ' + ', '.join(problems))
    print('Antigravity hooks.json, managed hooks and GEMINI.md OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['install', 'remove', 'check', 'validate'])
    parser.add_argument('--config', type=Path, default=gemini_dir() / 'config/hooks.json')
    args = parser.parse_args()
    try:
        if args.action == 'check':
            check(args.config)
        else:
            update(args.config, args.action == 'remove', args.action == 'validate')
    except (OSError, ValueError) as exc:
        raise SystemExit('Antigravity configuration error: ' + str(exc))
