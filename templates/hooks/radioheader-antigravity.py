#!/usr/bin/env python3
"""Antigravity CLI protocol adapter over RadioHeader's shared snapshot engine.

Verified against agy 1.5.14: hooks get camelCase stdin JSON (including an
undocumented "cwd"), run with the hooks.json directory as working
directory, answer with one JSON object on stdout, and a failing hook is
only logged (fail open, exit codes never block).
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
SNAPSHOTS = DATA / '.antigravity-turn-snapshots'


def engine(filename):
    spec = importlib.util.spec_from_file_location('radioheader_antigravity_engine', ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SNAPSHOT_DIR = SNAPSHOTS
    module.DIGEST_RUNTIME = 'antigravity'
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


def capture(func, payload):
    """Run an engine entry point without letting it write to agy's stdout."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        func(payload)
    return buffer.getvalue()


def project_dir(payload):
    # The hook process runs in the hooks.json directory, never the project.
    cwd = payload.get('cwd')
    if not cwd:
        paths = payload.get('workspacePaths') or []
        cwd = paths[0] if paths else os.getcwd()
    return Path(cwd).resolve()


def continuation_marker(payload):
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    return SNAPSHOTS / (payload['session_id'] + '.echo-requested')


def transcript_step(payload, step):
    """Return the transcript content recorded for a tool step, if any."""
    candidates = []
    if payload.get('transcriptPath'):
        given = Path(payload['transcriptPath'])
        candidates += [given, given.with_name('transcript.jsonl')]
    for path in candidates:
        try:
            with path.open('rb') as stream:
                stream.seek(0, os.SEEK_END)
                stream.seek(max(0, stream.tell() - 512 * 1024))
                lines = stream.read().decode('utf-8', 'replace').splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get('step_index') == step and isinstance(record.get('content'), str):
                return record['content']
    return ''


FAILURE_PATTERNS = [('fatal: not a git repository', 'not-a-git-repo'),
                    ('No such file or directory', 'file-not-found'),
                    ('command not found', 'command-not-found'),
                    ('Permission denied', 'permission-denied'),
                    ('Connection refused', 'network-error'), ('Could not resolve', 'network-error')]


def log_failure(payload, text):
    for symptom, pattern in FAILURE_PATTERNS:
        index = text.find(symptom)
        if index >= 0:
            DATA.mkdir(parents=True, exist_ok=True)
            snippet = text[max(0, index - 60):index + 60]
            with (DATA / 'error-log.jsonl').open('a') as f:
                f.write(json.dumps(dict(ts=datetime.datetime.now().isoformat(), pattern=pattern,
                    snippet=snippet, cwd=payload['cwd']), ensure_ascii=False) + '\n')
            return


def pending_steps(payload):
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    return SNAPSHOTS / (payload['session_id'] + '.pending-shell-steps')


def queue_shell_step(payload):
    """PostToolUse: the command's exit code is not in the payload and its
    transcript step is only written later, so queue the step for Stop."""
    call = payload.get('toolCall') or {}
    if call.get('name') != 'run_command':
        return
    if payload.get('error'):
        log_failure(payload, payload['error'])
    if isinstance(payload.get('stepIdx'), int):
        with pending_steps(payload).open('a') as stream:
            stream.write(str(payload['stepIdx']) + '\n')


def flush_shell_failures(payload):
    """Stop: by now the transcript holds each queued step's exit code."""
    path = pending_steps(payload)
    try:
        steps = {int(line) for line in path.read_text().split() if line.strip().isdigit()}
        path.unlink()
    except OSError:
        return
    for step in sorted(steps):
        content = transcript_step(payload, step)
        if re.search(r'Command exited with code (?!0\b)\d+', content):
            log_failure(payload, content)


def session_context(payload, cwd):
    message = run_script('radioheader-loader.sh', payload)
    message += run_script('check-project-architecture.sh', payload)
    memory = engine('radioheader-codex-userprompt.py').project_memory_dir(cwd) / 'MEMORY.md'
    try:
        # Antigravity does not auto-load Claude's canonical project memory.
        with memory.open() as stream:
            quickref = ''.join(line for _, line in zip(range(200), stream))[:8000]
        message += '\n--- project-memory: ' + str(memory) + ' ---\n' + quickref + '\n--- end project-memory ---\n'
    except OSError:
        pass
    return message


def main():
    payload = json.load(sys.stdin)
    event = sys.argv[1] if len(sys.argv) > 1 else payload.get('hookEventName')
    cwd = project_dir(payload)
    payload['cwd'] = str(cwd)
    # invocationNum/executionNum reset per user message and there is no turn
    # id, so one baseline per (hashed) conversation and project suffices.
    payload['session_id'] = hashlib.sha256(str(payload.get('conversationId', '')).encode()).hexdigest()[:24]
    payload['turn_id'] = 'current'
    output = {}
    if event == 'SessionStart':
        run_script('radioheader-git-sync.sh', payload, 'pull')
        context = session_context(payload, cwd)
        if context.strip():
            output = {'injectSteps': [{'systemMessage': {'systemMessage': context}}]}
    elif event == 'PreInvocation':
        # Fires per model call; invocationNum 0 is the first call for a new
        # user message. A Stop continuation re-enters with invocationNum > 0.
        if payload.get('invocationNum') == 0:
            with contextlib.suppress(OSError):
                continuation_marker(payload).unlink()
            capture(engine('radioheader-codex-userprompt.py').main, payload)
    elif event == 'Stop':
        flush_shell_failures(payload)
        stop = engine('radioheader-stop-codex.py')
        marker = continuation_marker(payload)
        # agy has no stop_hook_active (continuationActive stays false), so
        # guard the Echo continuation ourselves: request it at most once.
        if marker.exists() or (payload.get('executionNum') or 0) > 0:
            with contextlib.suppress(OSError):
                marker.unlink()
            with contextlib.suppress(OSError):
                stop.snapshot_name(payload['session_id'], payload['turn_id'], str(cwd)).unlink()
            run_script('radioheader-git-sync.sh', payload, 'push')
            output = {'decision': 'stop'}
        else:
            result = json.loads(capture(stop.main, payload) or '{}')
            if result.get('decision') == 'block':
                marker.touch()
                output = {'decision': 'continue', 'reason': result['reason']}
            else:
                run_script('radioheader-git-sync.sh', payload, 'push')
                output = {'decision': 'stop'}
    elif event == 'PostToolUse':
        queue_shell_step(payload)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print('RadioHeader Antigravity: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)  # agy logs failed hooks and continues (fail open).
