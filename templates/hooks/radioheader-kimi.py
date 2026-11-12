#!/usr/bin/env python3
"""Kimi Code 2.x protocol adapter over RadioHeader's shared snapshot engine."""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DATA = Path.home() / '.claude/radioheader'


def engine(filename):
    spec = importlib.util.spec_from_file_location('radioheader_kimi_engine', ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SNAPSHOT_DIR = DATA / '.kimi-turn-snapshots'
    module.DIGEST_RUNTIME = 'kimi'
    return module


def run_script(name, payload, *args):
    path = ROOT / name
    if not path.exists():
        return ''
    env = {**os.environ, 'CLAUDE_PROJECT_DIR': payload['cwd']}
    result = subprocess.run(['bash', str(path), *args], input=json.dumps(payload),
                            text=True, capture_output=True, cwd=payload['cwd'], env=env,
                            timeout=100 if 'git-sync' in name else 15)
    return result.stdout if result.returncode == 0 else ''


def record_failure(payload):
    if payload.get('tool_name') != 'Bash':
        return
    error = payload.get('error', '')
    text = error if isinstance(error, str) else json.dumps(error, ensure_ascii=False)
    patterns = [('fatal: not a git repository', 'not-a-git-repo'),
                ('No such file or directory', 'file-not-found'),
                ('command not found', 'command-not-found'),
                ('Permission denied', 'permission-denied'),
                ('Connection refused', 'network-error'), ('Could not resolve', 'network-error')]
    for symptom, pattern in patterns:
        if symptom in text:
            DATA.mkdir(parents=True, exist_ok=True)
            with (DATA / 'error-log.jsonl').open('a') as f:
                f.write(json.dumps(dict(ts=datetime.datetime.now().isoformat(), pattern=pattern,
                    snippet=text[:120], cwd=payload['cwd']), ensure_ascii=False) + '\n')
            break


def main():
    payload = json.load(sys.stdin)
    event = sys.argv[1] if len(sys.argv) > 1 else payload.get('hook_event_name')
    cwd = Path(payload.get('cwd') or os.getcwd()).resolve()
    payload['cwd'] = str(cwd)
    # Kimi 2.3 does not send turn_id in UserPromptSubmit or Stop. Its blocking
    # prompt hook provides a safe baseline before the loop starts. A steer
    # must not replace that baseline mid-turn. Keep one snapshot per session.
    payload['session_id'] = hashlib.sha256(str(payload.get('session_id', '')).encode()).hexdigest()[:24]
    payload['turn_id'] = 'current'
    if event == 'SessionStart':
        run_script('radioheader-git-sync.sh', payload, 'pull')
    elif event == 'UserPromptSubmit':
        if payload.get('is_steer'):
            return
        snapshot = engine('radioheader-codex-userprompt.py')
        snapshot.main(payload)
        # SessionStart is observation-only in Kimi: inject via the blocking
        # UserPromptSubmit path, whose message is actually added to context.
        message = run_script('radioheader-loader.sh', payload)
        message += run_script('check-project-architecture.sh', payload)
        memory = snapshot.project_memory_dir(cwd) / 'MEMORY.md'
        try:
            # Kimi does not auto-load Claude's canonical project memory.
            with memory.open() as stream:
                quickref = ''.join(line for _, line in zip(range(200), stream))[:8000]
            message += '\n--- project-memory: ' + str(memory) + ' ---\n' + quickref + '\n--- end project-memory ---\n'
        except OSError:
            pass
        print(json.dumps({'message': message}))
    elif event == 'Stop':
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            engine('radioheader-stop-codex.py').main(payload)
        output = json.loads(buffer.getvalue())
        if output.get('decision') == 'block':
            # Kimi does not implement Codex's decision/reason stdout schema.
            print(output['reason'], file=sys.stderr)
            raise SystemExit(2)
        run_script('radioheader-git-sync.sh', payload, 'push')
        print(json.dumps({'message': output.get('systemMessage', '')}))
    elif event == 'SessionEnd':
        # Kimi 2.3 runs Stop only once after a block; flush continuation edits
        # on close as well. The sync script keeps its own opt-in and lock.
        run_script('radioheader-git-sync.sh', payload, 'push')
    elif event == 'PostToolUseFailure':
        record_failure(payload)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('RadioHeader Kimi: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)  # Kimi's non-2 error path fails open.
