#!/usr/bin/env python3
"""Gemini CLI protocol adapter over RadioHeader's shared snapshot engine.

Gemini hooks: stdin JSON in, a single JSON object on stdout (any stray text
breaks parsing), stderr for diagnostics, timeouts in milliseconds.
"""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DATA = Path.home() / '.claude/radioheader'
SNAPSHOTS = DATA / '.gemini-turn-snapshots'


def engine(filename):
    spec = importlib.util.spec_from_file_location('radioheader_gemini_engine', ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SNAPSHOT_DIR = SNAPSHOTS
    module.DIGEST_RUNTIME = 'gemini'
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


def spawn_sync_push(payload):
    """SessionEnd is best effort: Gemini does not wait, so detach the push."""
    path = ROOT / 'radioheader-git-sync.sh'
    if not path.exists():
        return
    env = {**os.environ, 'CLAUDE_PROJECT_DIR': payload['cwd']}
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / '.gemini-sync.log').open('a') as log:
        subprocess.Popen(['bash', str(path), 'push'], stdin=subprocess.DEVNULL, stdout=log,
                         stderr=log, cwd=payload['cwd'], env=env, start_new_session=True)


def capture(func, payload):
    """Run an engine entry point without letting it write to Gemini's stdout."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        func(payload)
    return buffer.getvalue()


def record_failure(payload):
    if payload.get('tool_name') != 'run_shell_command':
        return
    response = payload.get('tool_response') or {}
    error = response.get('error')
    content = response.get('llmContent', '')
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    # Gemini reports a failed command in llmContent ("Exit Code: N"); a
    # successful command's output must not be mistaken for an error.
    failed = re.search(r'(?m)^Exit Code: (?!0\b)(?!\(none\))', content)
    if not error and not failed:
        return
    text = error.get('message', '') if isinstance(error, dict) else str(error or '')
    text = text or content
    patterns = [('fatal: not a git repository', 'not-a-git-repo'),
                ('No such file or directory', 'file-not-found'),
                ('command not found', 'command-not-found'),
                ('Permission denied', 'permission-denied'),
                ('Connection refused', 'network-error'), ('Could not resolve', 'network-error')]
    for symptom, pattern in patterns:
        index = text.find(symptom)
        if index >= 0:
            DATA.mkdir(parents=True, exist_ok=True)
            snippet = text[max(0, index - 60):index + 60]
            with (DATA / 'error-log.jsonl').open('a') as f:
                f.write(json.dumps(dict(ts=datetime.datetime.now().isoformat(), pattern=pattern,
                    snippet=snippet, cwd=payload['cwd']), ensure_ascii=False) + '\n')
            break


def session_context(payload, cwd):
    message = run_script('radioheader-loader.sh', payload)
    message += run_script('check-project-architecture.sh', payload)
    snapshot = engine('radioheader-codex-userprompt.py')
    memory = snapshot.project_memory_dir(cwd) / 'MEMORY.md'
    try:
        # Gemini does not auto-load Claude's canonical project memory.
        with memory.open() as stream:
            quickref = ''.join(line for _, line in zip(range(200), stream))[:8000]
        message += '\n--- project-memory: ' + str(memory) + ' ---\n' + quickref + '\n--- end project-memory ---\n'
    except OSError:
        pass
    return message


def main():
    payload = json.load(sys.stdin)
    event = sys.argv[1] if len(sys.argv) > 1 else payload.get('hook_event_name')
    cwd = Path(payload.get('cwd') or os.getcwd()).resolve()
    payload['cwd'] = str(cwd)
    # BeforeAgent/AfterAgent carry no turn id; Gemini fires them once per
    # user prompt, so one baseline per (hashed) session and project suffices.
    payload['session_id'] = hashlib.sha256(str(payload.get('session_id', '')).encode()).hexdigest()[:24]
    payload['turn_id'] = 'current'
    output = {}
    if event == 'SessionStart':
        if payload.get('source', 'startup') in ('startup', 'resume'):
            run_script('radioheader-git-sync.sh', payload, 'pull')
        # Interactive: first history turn; headless: prepended to the prompt.
        context = session_context(payload, cwd)
        if context.strip():
            output = {'hookSpecificOutput': {'hookEventName': 'SessionStart',
                                             'additionalContext': context}}
    elif event == 'BeforeAgent':
        capture(engine('radioheader-codex-userprompt.py').main, payload)
    elif event == 'AfterAgent':
        stop = engine('radioheader-stop-codex.py')
        if payload.get('stop_hook_active'):
            # Second pass after an Echo retry. Gemini re-fires BeforeAgent for
            # the retry prompt; discard that baseline instead of re-checking.
            path = stop.snapshot_name(payload['session_id'], payload['turn_id'], str(cwd))
            with contextlib.suppress(OSError):
                path.unlink()
            run_script('radioheader-git-sync.sh', payload, 'push')
        else:
            result = json.loads(capture(stop.main, payload) or '{}')
            if result.get('decision') == 'block':
                # Gemini's AfterAgent deny sends reason back as a retry prompt.
                output = {'decision': 'deny', 'reason': result['reason']}
            else:
                run_script('radioheader-git-sync.sh', payload, 'push')
                if result.get('systemMessage'):
                    output = {'systemMessage': result['systemMessage']}
    elif event == 'SessionEnd':
        spawn_sync_push(payload)
    elif event == 'AfterTool':
        record_failure(payload)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print('RadioHeader Gemini: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)  # Non-2 exit codes are warnings: Gemini fails open.
