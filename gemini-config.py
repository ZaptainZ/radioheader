#!/usr/bin/env python3
"""Manage only RadioHeader's Gemini CLI hooks in settings.json.

Ownership is decided by the exact adapter command (JSON has no comments to
carry markers, and Gemini rewrites settings.json from its /settings UI).
Every other key, hook group and hook entry is preserved; the result is
verified semantically before an atomic replace with a private backup.
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

SCRIPT_NAME = 'radioheader-gemini.py'
# event -> (matcher, timeout in milliseconds; Gemini uses ms, not seconds)
EVENTS = {
    'SessionStart': (None, 30000),
    'BeforeAgent': (None, 30000),
    'AfterAgent': (None, 120000),
    'AfterTool': ('run_shell_command', 15000),
    'SessionEnd': (None, 15000),
}


def gemini_dir():
    # GEMINI_CLI_HOME replaces the *home* directory; Gemini appends .gemini.
    return Path(os.environ.get('GEMINI_CLI_HOME') or Path.home()) / '.gemini'


def script_path():
    return Path.home() / '.claude/hooks' / SCRIPT_NAME


def expected_groups():
    groups = {}
    for event, (matcher, timeout) in EVENTS.items():
        hook = dict(name='radioheader-' + event, type='command',
                    command=shlex.quote(sys.executable) + ' ' + shlex.quote(str(script_path())) + ' ' + event,
                    timeout=timeout)
        group = {'matcher': matcher} if matcher else {}
        group['hooks'] = [hook]
        groups[event] = group
    return groups


def owned(hook):
    if not isinstance(hook, dict):
        return False
    try:
        args = shlex.split(str(hook.get('command', '')))
    except ValueError:
        return False
    return len(args) == 3 and Path(args[1]) == script_path() and args[2] in EVENTS


def load(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text())  # comments/trailing commas are refused
    if not isinstance(data, dict):
        raise ValueError('settings.json root must be an object')
    hooks = data.get('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('settings.json "hooks" must be an object')
    for event, groups in hooks.items():
        if not isinstance(groups, list) or not all(isinstance(g, dict) for g in groups):
            raise ValueError('settings.json hooks.' + event + ' must be a list of hook groups')
        for group in groups:
            if not isinstance(group.get('hooks', []), list):
                raise ValueError('settings.json hooks.' + event + '[].hooks must be a list')
    return data


def without_owned(data):
    result = copy.deepcopy(data)
    hooks = result.get('hooks')
    if not isinstance(hooks, dict):
        return result
    for event in list(hooks):
        kept_groups = []
        for group in hooks[event]:
            entries = group.get('hooks', [])
            kept = [h for h in entries if not owned(h)]
            if entries and not kept:
                continue  # group held only RadioHeader hooks
            if len(kept) != len(entries):
                group = dict(group, hooks=kept)
            kept_groups.append(group)
        if hooks[event] and not kept_groups:
            del hooks[event]
        else:
            hooks[event] = kept_groups
    if data.get('hooks') and not hooks:
        del result['hooks']
    return result


def canonical(data):
    """Unrelated settings, ignoring empty hook containers Gemini treats as absent."""
    result = without_owned(data)
    hooks = result.get('hooks')
    if isinstance(hooks, dict):
        hooks = {event: groups for event, groups in hooks.items() if groups}
        if hooks:
            result['hooks'] = hooks
        else:
            result.pop('hooks')
    return result


def build(data, remove=False):
    result = without_owned(data)
    if not remove:
        hooks = result.setdefault('hooks', {})
        for event, group in expected_groups().items():
            hooks.setdefault(event, []).append(group)
    return result


def owned_hooks(data):
    return {event: [h for g in groups for h in g.get('hooks', []) if owned(h)]
            for event, groups in data.get('hooks', {}).items()}


def update(path, remove=False, dry_run=False):
    raw = path.read_text() if path.exists() else None
    data = load(path)
    result = build(data, remove)
    # Unrelated settings must survive exactly; owned hooks must match.
    if canonical(result) != canonical(data):
        raise ValueError('Cannot safely preserve custom settings; settings.json was not changed.')
    expected = {} if remove else {e: g['hooks'] for e, g in expected_groups().items()}
    if {e: h for e, h in owned_hooks(result).items() if h} != expected:
        raise ValueError('Cannot safely replace managed hooks; settings.json was not changed.')
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if dry_run or result == data or (raw is None and remove):
        return
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


def check(path):
    data = load(path)
    problems = []
    current = owned_hooks(data)
    for event, group in expected_groups().items():
        if group['hooks'][0] not in current.get(event, []):
            problems.append(event)
    config = data.get('hooksConfig', {})
    if isinstance(config, dict):
        if config.get('enabled') is False:
            problems.append('hooksConfig.enabled=false')
        disabled = config.get('disabled') or []
        if any(str(item).startswith('radioheader-') or SCRIPT_NAME in str(item) for item in disabled):
            problems.append('hooksConfig.disabled lists RadioHeader hooks')
    hooks_dir = script_path().parent
    for name in (SCRIPT_NAME, 'radioheader-codex-userprompt.py', 'radioheader-stop-codex.py'):
        if not (hooks_dir / name).is_file():
            problems.append(name)
    rules = path.parent / 'GEMINI.md'
    if not rules.exists() or 'RadioHeader START' not in rules.read_text():
        problems.append('GEMINI.md rules')
    if problems:
        raise ValueError('Gemini missing/mismatched: ' + ', '.join(problems))
    print('Gemini settings, managed hooks and GEMINI.md OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['install', 'remove', 'check', 'validate'])
    parser.add_argument('--config', type=Path, default=gemini_dir() / 'settings.json')
    args = parser.parse_args()
    try:
        if args.action == 'check':
            check(args.config)
        else:
            update(args.config, args.action == 'remove', args.action == 'validate')
    except (OSError, ValueError) as exc:
        # json errors report position only, never the settings content.
        raise SystemExit('Gemini configuration error: ' + str(exc))
