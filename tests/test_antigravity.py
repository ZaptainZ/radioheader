"""Antigravity CLI hooks.json preservation and lifecycle protocol tests; no network or credentials.

Payload shapes mirror what agy 1.5.14 actually sent in local runs: camelCase
fields, an undocumented "cwd", per-message invocationNum/executionNum, and a
Stop continuation that re-enters with executionNum 1 and continuationActive false.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AntigravityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rh-agy-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        harness = self.home / 'uninstall-harness'
        harness.mkdir()
        self.uninstaller = harness / 'uninstall.sh'
        self.uninstaller.write_text((ROOT / 'uninstall.sh').read_text().replace('/usr/local/bin', str(self.home / 'system-bin')))
        # The uninstaller calls every runtime's config helper next to itself.
        for helper in ROOT.glob('*-config.py'):
            shutil.copy2(helper, harness / helper.name)
        self.gemini = self.home / '.gemini'
        (self.gemini / 'config').mkdir(parents=True)
        self.hooks_json = self.gemini / 'config/hooks.json'
        self.original = {'my-linter': {'PostToolUse': [{'matcher': 'write_file', 'hooks': [{'type': 'command', 'command': 'echo lint'}]}]},
                         'reminder': {'enabled': False, 'Stop': [{'type': 'command', 'command': 'echo bye'}]}}
        self.hooks_json.write_text(json.dumps(self.original, indent=4))
        self.hooks_json.chmod(0o640)
        self.data = self.home / '.claude/radioheader'
        self.hooks = self.home / '.claude/hooks'
        self.hooks.mkdir(parents=True)
        for p in (ROOT / 'templates/hooks').glob('*'):
            if p.is_file(): shutil.copy2(p, self.hooks / p.name)
        for d in ['topics', 'shortwave']: (self.data / d).mkdir(parents=True)
        self.project = self.home / 'project'
        self.project.mkdir()
        self.memory = self.home / '.claude/projects' / re.sub(r'[^a-zA-Z0-9_-]', '-', str(self.project)) / 'memory'
        self.memory.mkdir(parents=True)
        (self.data / 'context-digest.md').write_text('AGY_DIGEST_PROBE')
        (self.data / 'project-registry.json').write_text('{"projects":[]}')
        (self.data / 'config.json').write_text('{"auto_digest":false}')
        (self.home / 'bin').mkdir()
        self.env = {**os.environ, 'HOME': str(self.home), 'GEMINI_CLI_HOME': str(self.home),
                    'KIMI_CODE_HOME': str(self.home / '.kimi-code'),
                    'RADIOHEADER_DIR': str(self.data), 'RADIOHEADER_AUTO_DIGEST': '0',
                    'RADIOHEADER_RADIOMIND_AUTO': '0', 'PATH': str(self.home / 'bin') + ':' + os.environ['PATH']}
        self.stub('radiomind', 'exit 1')
        (self.hooks / 'radioheader-git-sync.sh').write_text('echo "$1" >> "$HOME/sync-events"\n')
        (self.hooks / 'check-project-architecture.sh').write_text('echo ARCHITECTURE_PROBE\n')
        self.transcript = self.home / 'brain/conv/.system_generated/logs/transcript.jsonl'
        self.transcript.parent.mkdir(parents=True)

    def stub(self, name, body):
        p = self.home / 'bin' / name
        p.write_text('#!/bin/sh\n' + body + '\n'); p.chmod(0o755)

    def run_cmd(self, *args, input=None, cwd=None):
        return subprocess.run(args, env=self.env, cwd=cwd or self.project, input=input,
                              text=True, capture_output=True, timeout=90)

    def config_cmd(self, action='install'):
        return self.run_cmd(sys.executable, str(ROOT / 'antigravity-config.py'), action)

    def event(self, event, conversation='conv-1', **extra):
        payload = dict(conversationId=conversation, cwd=str(self.project), workspacePaths=[str(self.project)],
                       hookEventName=event, lastUserInput='hi', modelName='gemini-3.1-pro-low',
                       transcriptPath=str(self.transcript.with_name('transcript_full.jsonl')),
                       artifactDirectoryPath=str(self.home / 'brain/conv'), **extra)
        # agy runs hooks in the hooks.json directory, not the project.
        return self.run_cmd(sys.executable, str(self.hooks / 'radioheader-antigravity.py'), event,
                            input=json.dumps(payload), cwd=self.gemini / 'config')

    def output(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def install(self, runtime='antigravity'):
        r = self.run_cmd('bash', str(ROOT / 'install.sh'), '--yes', '--runtime', runtime, '--bin-dir', str(self.home / 'bin'))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def hooks_data(self):
        return json.loads(self.hooks_json.read_text())

    def stop(self, execution=0):
        return self.output(self.event('Stop', executionNum=execution, terminationReason='NO_TOOL_CALL',
                                      error='', fullyIdle=True, continuationActive=False))

    def test_config_preserves_other_hooks_and_is_idempotent(self):
        self.assertEqual(self.config_cmd().returncode, 0)
        data = self.hooks_data()
        self.assertEqual({k: v for k, v in data.items() if k != 'radioheader'}, self.original)
        entry = data['radioheader']
        self.assertEqual(set(entry), {'SessionStart', 'PreInvocation', 'Stop', 'PostToolUse'})
        self.assertEqual(entry['PostToolUse'][0]['matcher'], 'run_command')
        self.assertTrue(all(h['timeout'] <= 120 for e in ('SessionStart', 'PreInvocation', 'Stop') for h in entry[e]))
        self.assertEqual(self.hooks_json.stat().st_mode & 0o777, 0o640)
        first = self.hooks_json.read_text()
        self.assertEqual(self.config_cmd().returncode, 0)
        self.assertEqual(self.hooks_json.read_text(), first)
        self.assertEqual(len(list(self.hooks_json.parent.glob('*.bak.*'))), 1)
        self.assertEqual(self.config_cmd('check').returncode != 0, True)  # GEMINI.md rules not installed yet
        self.assertEqual(self.config_cmd('remove').returncode, 0)
        self.assertEqual(self.hooks_data(), self.original)

    def test_user_disable_survives_reinstall(self):
        self.config_cmd()
        data = self.hooks_data()
        data['radioheader'] = dict(enabled=False, **data['radioheader'])
        self.hooks_json.write_text(json.dumps(data))
        self.assertEqual(self.config_cmd().returncode, 0)
        self.assertIs(self.hooks_data()['radioheader']['enabled'], False)

    def test_check_flags_missing_interpreter_but_not_a_different_one(self):
        self.install()
        data = self.hooks_data()
        for handler in data['radioheader']['Stop']:
            handler['command'] = handler['command'].replace(handler['command'].split(' ')[0], '/usr/bin/python3', 1)
        self.hooks_json.write_text(json.dumps(data))
        self.assertEqual(self.config_cmd('check').returncode, 0)
        for handler in data['radioheader']['Stop']:
            handler['command'] = '/nonexistent/python3 ' + handler['command'].split(' ', 1)[1]
        self.hooks_json.write_text(json.dumps(data))
        r = self.config_cmd('check')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('interpreter missing', r.stderr)

    def test_foreign_radioheader_entry_and_invalid_json_refused(self):
        for raw in ['{"radioheader": {"Stop": [{"type": "command", "command": "echo mine"}]}}',
                    '{"secret": "unfinished', '// c\n{}', '[]', '{"a": 1}']:
            self.hooks_json.write_text(raw)
            r = self.config_cmd()
            self.assertNotEqual(r.returncode, 0, raw)
            self.assertEqual(self.hooks_json.read_text(), raw)
            self.assertNotIn('unfinished', r.stderr)

    def test_install_init_doctor_and_partial_uninstall(self):
        self.install()
        self.assertFalse((self.home / '.claude/settings.json').exists())
        self.assertFalse((self.gemini / 'settings.json').exists())
        self.assertEqual((self.gemini / 'GEMINI.md').read_text().count('RadioHeader START'), 1)
        self.assertEqual(self.config_cmd('check').returncode, 0)
        cli = str(self.home / 'bin/radioheader')
        r = self.run_cmd(cli, 'init', '--runtime', 'antigravity', '--name', 'AgyProbe', '--stack', 'Python')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('AgyProbe', (self.project / 'GEMINI.md').read_text())
        self.assertFalse((self.project / 'AGENTS.md').exists())
        self.assertIn('antigravity', self.run_cmd(cli, 'status').stdout.lower())
        self.assertEqual(self.run_cmd(cli, 'index', '--rebuild').returncode, 0)
        r = self.run_cmd(cli, 'doctor')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('Antigravity runtime configured', r.stdout)
        r = self.run_cmd('bash', str(self.uninstaller), '--runtime', 'antigravity')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.hooks_data(), self.original)
        self.assertNotIn('RadioHeader START', (self.gemini / 'GEMINI.md').read_text())
        self.assertTrue(Path(cli).exists())
        self.assertFalse((self.hooks / 'radioheader-antigravity.py').exists())

    def test_gemini_and_antigravity_share_rules_section(self):
        self.install('all')
        self.assertEqual((self.gemini / 'GEMINI.md').read_text().count('RadioHeader START'), 1)
        self.install('antigravity')
        self.assertEqual((self.gemini / 'GEMINI.md').read_text().count('RadioHeader START'), 1)
        r = self.run_cmd('bash', str(self.uninstaller), '--runtime', 'gemini')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.config_cmd('check').returncode, 0)  # rules kept for Antigravity
        r = self.run_cmd('bash', str(self.uninstaller), '--runtime', 'both', input='n\n')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.home / 'bin/antigravity-config.py').exists())
        self.assertTrue((self.hooks / 'radioheader-stop-codex.py').exists())
        r = self.run_cmd('bash', str(self.uninstaller), '--runtime', 'all', input='n\n')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.hooks_data(), self.original)
        self.assertNotIn('RadioHeader START', (self.gemini / 'GEMINI.md').read_text())
        self.assertFalse((self.hooks / 'radioheader-antigravity.py').exists())

    def test_session_start_injects_steps(self):
        (self.memory / 'MEMORY.md').write_text('PROJECT_MEMORY_PROBE\n' + 'bounded\n' * 205)
        out = self.output(self.event('SessionStart'))
        context = out['injectSteps'][0]['systemMessage']['systemMessage']
        for probe in ('AGY_DIGEST_PROBE', 'ARCHITECTURE_PROBE', 'PROJECT_MEMORY_PROBE'):
            self.assertIn(probe, context)
        self.assertEqual(context.count('bounded'), 199)
        self.assertEqual((self.home / 'sync-events').read_text(), 'pull\n')

    def test_snapshot_only_on_first_invocation_of_a_message(self):
        self.assertEqual(self.output(self.event('PreInvocation', invocationNum=0, initialNumSteps=1)), {})
        snaps = list((self.data / '.antigravity-turn-snapshots').glob('*.json'))
        self.assertEqual(len(snaps), 1)
        before = snaps[0].read_text()
        (self.memory / 'mid.md').write_text('changed mid-turn')
        self.assertEqual(self.output(self.event('PreInvocation', invocationNum=1, initialNumSteps=4)), {})
        self.assertEqual(snaps[0].read_text(), before)
        self.assertFalse((self.data / '.gemini-turn-snapshots').exists())

    def test_stop_continues_once_then_allows_and_syncs(self):
        self.event('PreInvocation', invocationNum=0)
        (self.memory / 'topic.md').write_text('new lesson')
        out = self.stop(0)
        self.assertEqual(out['decision'], 'continue')
        self.assertIn('global RadioHeader topic', out['reason'])
        self.assertFalse((self.home / 'sync-events').exists())
        self.event('PreInvocation', invocationNum=1)  # continuation re-entry
        self.assertEqual(self.stop(1)['decision'], 'stop')
        self.assertEqual((self.home / 'sync-events').read_text(), 'push\n')
        self.assertEqual(list((self.data / '.antigravity-turn-snapshots').glob('*')), [])

    def test_marker_guard_even_if_execution_num_does_not_advance(self):
        self.event('PreInvocation', invocationNum=0)
        (self.data / 'topics/lesson.md').write_text('new')
        out = self.stop(0)
        self.assertEqual(out['decision'], 'continue')
        self.assertIn('shortwave', out['reason'])
        self.assertEqual(self.stop(0)['decision'], 'stop')

    def test_next_message_gets_fresh_baseline_and_guard(self):
        self.event('PreInvocation', invocationNum=0)
        (self.memory / 'a.md').write_text('1')
        self.assertEqual(self.stop(0)['decision'], 'continue')
        # User never satisfies Echo; next message must start clean.
        self.event('PreInvocation', invocationNum=0)
        (self.memory / 'b.md').write_text('2')
        self.assertEqual(self.stop(0)['decision'], 'continue')

    def test_conversations_are_isolated(self):
        self.event('PreInvocation', conversation='A', invocationNum=0)
        self.event('PreInvocation', conversation='B', invocationNum=0)
        (self.memory / 'x.md').write_text('x')
        self.assertEqual(self.output(self.event('Stop', conversation='A', executionNum=0, fullyIdle=True))['decision'], 'continue')
        self.assertEqual(self.output(self.event('Stop', conversation='B', executionNum=0, fullyIdle=True))['decision'], 'continue')

    def test_complete_echo_counts_antigravity_only(self):
        self.env['RADIOHEADER_AUTO_DIGEST'] = '1'
        (self.data / 'config.json').write_text('{}')
        self.stub('radioheader', 'echo "$*" >> "$HOME/consolidated"')
        for i in range(5):
            self.event('PreInvocation', invocationNum=0)
            for root in [self.memory, self.data / 'topics', self.data / 'shortwave']:
                (root / 'lesson.md').write_text(str(i) * (i + 1))
            self.assertEqual(self.stop(0)['decision'], 'stop')
        deadline = time.monotonic() + 5
        while not (self.home / 'consolidated').exists() and time.monotonic() < deadline: time.sleep(.02)
        self.assertEqual((self.home / 'consolidated').read_text(), 'consolidate --native\n')
        self.assertEqual((self.data / '.antigravity-consolidate-counter').read_text().strip(), '0')
        self.assertFalse((self.data / '.gemini-consolidate-counter').exists())

    def test_shell_failure_read_from_transcript_at_stop(self):
        call = {'name': 'run_command', 'args': {'CommandLine': 'ls x'}, 'id': '1'}
        # agy writes the tool step to the transcript only after PostToolUse.
        self.transcript.write_text(json.dumps({'step_index': 2, 'type': 'PLANNER_RESPONSE'}) + '\n')
        self.output(self.event('PostToolUse', toolCall=call, stepIdx=3, error=''))
        self.output(self.event('PostToolUse', toolCall=call, stepIdx=5, error=''))
        self.output(self.event('PostToolUse', toolCall={'name': 'read_file', 'args': {}}, stepIdx=6, error='Permission denied'))
        self.assertFalse((self.data / 'error-log.jsonl').exists())
        steps = [{'step_index': 2, 'type': 'PLANNER_RESPONSE'},
                 {'step_index': 3, 'type': 'GENERIC', 'content': 'Command exited with code 1.\n\nCommand output:\nls: x: No such file or directory\r\n'},
                 {'step_index': 5, 'type': 'GENERIC', 'content': 'Command exited with code 0.\n\nCommand output:\ndocs mention No such file or directory\n'}]
        self.transcript.write_text('\n'.join(json.dumps(x) for x in steps) + '\n')
        self.stop(0)
        self.stop(0)  # queued steps are consumed once
        lines = (self.data / 'error-log.jsonl').read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])['pattern'], 'file-not-found')

    def test_antigravity_only_sync_does_not_enable_other_runtimes(self):
        self.install()
        cli = str(self.home / 'bin/radioheader')
        vault = self.home / 'vault.git'
        self.assertEqual(self.run_cmd('git', 'init', '--bare', str(vault)).returncode, 0)
        r = self.run_cmd(cli, 'device-sync', 'init', '--remote', str(vault))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.home / '.claude/settings.json').exists())
        self.assertFalse((self.home / '.codex/hooks.json').exists())
        for path in ['.antigravity-turn-snapshots/x.echo-requested', '.antigravity-consolidate-counter', '.antigravity-consolidate.log']:
            self.assertEqual(self.run_cmd('git', 'check-ignore', path, cwd=self.data).returncode, 0, path)
        self.run_cmd(cli, 'index', '--rebuild')
        r = self.run_cmd(cli, 'doctor')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__': unittest.main()
