"""Gemini CLI settings preservation and lifecycle protocol tests; no network or credentials."""
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


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rh-gemini-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        # Redirect the fixed /usr/local/bin path so tests can never remove a
        # developer machine's real CLI, even though HOME is isolated.
        harness = self.home / 'uninstall-harness'
        harness.mkdir()
        self.uninstaller = harness / 'uninstall.sh'
        self.uninstaller.write_text((ROOT / 'uninstall.sh').read_text().replace('/usr/local/bin', str(self.home / 'system-bin')))
        for helper in ('kimi-config.py', 'gemini-config.py'):
            shutil.copy2(ROOT / helper, harness / helper)
        self.gemini = self.home / '.gemini'
        self.gemini.mkdir()
        self.settings = self.gemini / 'settings.json'
        self.original = {
            'model': {'name': 'custom-model'},
            'security': {'auth': {'selectedType': 'oauth-personal'}},
            'hooks': {'AfterAgent': [{'hooks': [{'type': 'command', 'command': 'echo custom', 'name': 'mine'}]}]},
        }
        self.settings.write_text(json.dumps(self.original, indent=4))
        self.settings.chmod(0o640)
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
        (self.data / 'context-digest.md').write_text('GEMINI_DIGEST_PROBE')
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

    def stub(self, name, body):
        p = self.home / 'bin' / name
        p.write_text('#!/bin/sh\n' + body + '\n'); p.chmod(0o755)

    def run_cmd(self, *args, input=None, cwd=None):
        return subprocess.run(args, env=self.env, cwd=cwd or self.project, input=input,
                              text=True, capture_output=True, timeout=90)

    def config_cmd(self, action='install'):
        return self.run_cmd(sys.executable, str(ROOT / 'gemini-config.py'), action)

    def event(self, event, **extra):
        payload = dict(cwd=str(self.project), session_id='../../session', hook_event_name=event,
                       transcript_path='/dev/null', timestamp='2026-11-23T00:00:00Z', **extra)
        return self.run_cmd(sys.executable, str(self.hooks / 'radioheader-gemini.py'), event,
                            input=json.dumps(payload))

    def output(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)  # stdout must be exactly one JSON object

    def install(self, runtime='gemini'):
        r = self.run_cmd('bash', str(ROOT / 'install.sh'), '--yes', '--runtime', runtime, '--bin-dir', str(self.home / 'bin'))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def settings_data(self):
        return json.loads(self.settings.read_text())

    def test_config_preserves_user_values_and_is_idempotent(self):
        self.assertEqual(self.config_cmd().returncode, 0)
        data = self.settings_data()
        self.assertEqual(data['model'], self.original['model'])
        self.assertEqual(data['security'], self.original['security'])
        self.assertEqual(len(data['hooks']['AfterAgent']), 2)
        self.assertEqual(data['hooks']['AfterAgent'][0], self.original['hooks']['AfterAgent'][0])
        self.assertEqual(set(data['hooks']), {'SessionStart', 'BeforeAgent', 'AfterAgent', 'AfterTool', 'SessionEnd'})
        self.assertEqual(data['hooks']['AfterTool'][-1]['matcher'], 'run_shell_command')
        self.assertTrue(all(g['hooks'][0]['timeout'] >= 1000 for e in data['hooks'].values() for g in e if 'name' in g['hooks'][0] and g['hooks'][0]['name'].startswith('radioheader-')))
        self.assertEqual(self.settings.stat().st_mode & 0o777, 0o640)
        first = self.settings.read_text()
        self.assertEqual(self.config_cmd().returncode, 0)
        self.assertEqual(self.settings.read_text(), first)
        backups = list(self.gemini.glob('*.bak.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.config_cmd('remove').returncode, 0)
        self.assertEqual(self.settings_data(), self.original)

    def test_missing_settings_created_and_removed_cleanly(self):
        self.settings.unlink()
        self.assertEqual(self.config_cmd().returncode, 0)
        self.assertEqual(self.settings.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.config_cmd('remove').returncode, 0)
        self.assertEqual(self.settings_data(), {})

    def test_user_hook_in_shared_group_survives(self):
        self.config_cmd()
        data = self.settings_data()
        data['hooks']['BeforeAgent'][-1]['hooks'].append({'type': 'command', 'command': 'echo keep-me'})
        self.settings.write_text(json.dumps(data))
        self.assertEqual(self.config_cmd().returncode, 0)
        self.assertEqual(self.config_cmd('remove').returncode, 0)
        kept = self.settings_data()['hooks']['BeforeAgent']
        self.assertEqual(kept, [{'hooks': [{'type': 'command', 'command': 'echo keep-me'}]}])

    def test_invalid_settings_refused_unchanged(self):
        for raw in ['{"secret": "unfinished', '// comment\n{"a": 1}', '[]', '{"hooks": []}', '{"hooks": {"AfterAgent": {}}}']:
            self.settings.write_text(raw)
            r = self.config_cmd()
            self.assertNotEqual(r.returncode, 0, raw)
            self.assertEqual(self.settings.read_text(), raw)
            self.assertNotIn('unfinished', r.stderr)

    def test_installer_invalid_settings_leaves_other_runtimes_untouched(self):
        self.settings.write_text('{invalid')
        r = self.run_cmd('bash', str(ROOT / 'install.sh'), '--yes', '--runtime', 'all', '--bin-dir', str(self.home / 'bin'))
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.home / '.codex/AGENTS.md').exists())
        self.assertFalse((self.home / '.claude/CLAUDE.md').exists())
        self.assertFalse((self.home / '.kimi-code/AGENTS.md').exists())

    def test_install_init_doctor_upgrade_and_partial_uninstall(self):
        self.install()
        self.assertFalse((self.home / '.claude/settings.json').exists())
        self.assertFalse((self.home / '.codex/hooks.json').exists())
        self.assertIn('RadioHeader START', (self.gemini / 'GEMINI.md').read_text())
        self.assertEqual(self.config_cmd('check').returncode, 0)
        cli = str(self.home / 'bin/radioheader')
        r = self.run_cmd(cli, 'init', '--runtime', 'gemini', '--name', 'GeminiProbe', '--stack', 'Python')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        entry = self.project / 'GEMINI.md'
        self.assertIn('GeminiProbe', entry.read_text())
        self.assertFalse((self.project / '.codex').exists())
        self.assertFalse((self.project / 'CLAUDE.md').exists())
        self.assertFalse((self.project / 'AGENTS.md').exists())
        self.assertIn('gemini', self.run_cmd(cli, 'status').stdout.lower())
        self.assertEqual(self.run_cmd(cli, 'index', '--rebuild').returncode, 0)
        r = self.run_cmd(cli, 'doctor')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('Gemini runtime configured', r.stdout)
        entry.write_text(entry.read_text() + '\nCustom Gemini guidance\n')
        self.assertEqual(self.run_cmd(cli, 'upgrade', 'GeminiProbe').returncode, 0)
        self.assertIn('Custom Gemini guidance', entry.read_text())
        (self.project / '.gemini').mkdir()
        entry.unlink()
        self.assertEqual(self.run_cmd(cli, 'upgrade', 'GeminiProbe').returncode, 0)
        self.assertTrue(entry.exists())
        r = self.run_cmd('bash', str(self.uninstaller), '--runtime', 'gemini')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.settings_data(), self.original)
        self.assertNotIn('RadioHeader START', (self.gemini / 'GEMINI.md').read_text())
        self.assertTrue(Path(cli).exists())
        self.assertTrue((self.hooks / 'radioheader-stop-codex.py').exists())
        self.assertFalse((self.hooks / 'radioheader-gemini.py').exists())

    def test_doctor_flags_disabled_hooks(self):
        self.install()
        data = self.settings_data()
        data['hooksConfig'] = {'enabled': False}
        self.settings.write_text(json.dumps(data))
        r = self.config_cmd('check')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('hooksConfig.enabled', r.stderr)

    def test_uninstall_both_and_kimi_preserve_installed_gemini(self):
        self.install('all')
        for runtime in ('both', 'kimi'):
            r = self.run_cmd('bash', str(self.uninstaller), '--runtime', runtime, input='n\n')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(self.config_cmd('check').returncode, 0, runtime)
            self.assertTrue((self.home / 'bin/radioheader').exists())
            self.assertTrue((self.home / 'bin/gemini-config.py').exists())
            self.assertTrue((self.hooks / 'radioheader-stop-codex.py').exists())

    def test_full_uninstall_removes_all_owned_adapters(self):
        self.install('all')
        (self.data / 'topics/keep.md').write_text('user knowledge')
        r = self.run_cmd('bash', str(self.uninstaller), '--runtime', 'all', input='n\n')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.settings_data(), self.original)
        self.assertFalse((self.hooks / 'radioheader-gemini.py').exists())
        self.assertFalse((self.home / 'bin/gemini-config.py').exists())
        self.assertTrue((self.data / 'topics/keep.md').exists())

    def test_session_start_injects_context_and_pulls_once(self):
        (self.memory / 'MEMORY.md').write_text('PROJECT_MEMORY_PROBE\n' + 'bounded\n' * 205)
        out = self.output(self.event('SessionStart', source='startup'))
        context = out['hookSpecificOutput']['additionalContext']
        for probe in ('GEMINI_DIGEST_PROBE', 'ARCHITECTURE_PROBE', 'PROJECT_MEMORY_PROBE'):
            self.assertIn(probe, context)
        self.assertEqual(context.count('bounded'), 199)
        self.output(self.event('SessionStart', source='clear'))
        self.assertEqual((self.home / 'sync-events').read_text(), 'pull\n')

    def test_before_agent_snapshot_is_silent_and_isolated(self):
        self.assertEqual(self.output(self.event('BeforeAgent', prompt='hi')), {})
        self.assertEqual(len(list((self.data / '.gemini-turn-snapshots').glob('*.json'))), 1)
        self.assertFalse((self.data / '.codex-turn-snapshots').exists())
        self.assertFalse((self.data / '.kimi-turn-snapshots').exists())

    def test_after_agent_denies_once_then_retry_pass_syncs(self):
        self.event('BeforeAgent', prompt='work')
        (self.memory / 'topic.md').write_text('new lesson')
        out = self.output(self.event('AfterAgent', prompt='work', prompt_response='done', stop_hook_active=False))
        self.assertEqual(out['decision'], 'deny')
        self.assertIn('global RadioHeader topic', out['reason'])
        self.assertFalse((self.home / 'sync-events').exists())
        # Gemini re-fires BeforeAgent for the retry prompt, then AfterAgent
        # with stop_hook_active; that pass must not block again.
        self.event('BeforeAgent', prompt=out['reason'])
        self.assertEqual(self.output(self.event('AfterAgent', stop_hook_active=True)), {})
        self.assertEqual(list((self.data / '.gemini-turn-snapshots').glob('*')), [])
        self.assertEqual((self.home / 'sync-events').read_text(), 'push\n')

    def test_topic_change_requires_shortwave(self):
        self.event('BeforeAgent', prompt='x')
        (self.data / 'topics/lesson.md').write_text('new')
        out = self.output(self.event('AfterAgent', stop_hook_active=False))
        self.assertEqual(out['decision'], 'deny')
        self.assertIn('shortwave', out['reason'])

    def test_complete_echo_continues_and_counts_gemini_only(self):
        self.env['RADIOHEADER_AUTO_DIGEST'] = '1'
        (self.data / 'config.json').write_text('{}')
        self.stub('radioheader', 'echo "$*" >> "$HOME/consolidated"')
        for i in range(5):
            self.event('BeforeAgent', prompt=str(i))
            for root in [self.memory, self.data / 'topics', self.data / 'shortwave']:
                (root / 'lesson.md').write_text(str(i) * (i + 1))
            out = self.output(self.event('AfterAgent', stop_hook_active=False))
            self.assertNotEqual(out.get('decision'), 'deny')
        deadline = time.monotonic() + 5
        while not (self.home / 'consolidated').exists() and time.monotonic() < deadline: time.sleep(.02)
        self.assertEqual((self.home / 'consolidated').read_text(), 'consolidate --native\n')
        self.assertEqual((self.data / '.gemini-consolidate-counter').read_text().strip(), '0')
        self.assertFalse((self.data / '.codex-consolidate-counter').exists())

    def test_session_end_pushes_in_background(self):
        self.assertEqual(self.output(self.event('SessionEnd', reason='exit')), {})
        deadline = time.monotonic() + 5
        while not (self.home / 'sync-events').exists() and time.monotonic() < deadline: time.sleep(.02)
        self.assertEqual((self.home / 'sync-events').read_text(), 'push\n')

    def test_shell_failure_logged_but_successful_output_ignored(self):
        failed = 'Output: cat: x: No such file or directory\nExit Code: 1\nSignal: (none)'
        self.output(self.event('AfterTool', tool_name='run_shell_command', tool_input={'command': 'cat x'},
                               tool_response={'llmContent': failed, 'returnDisplay': failed}))
        self.output(self.event('AfterTool', tool_name='run_shell_command', tool_input={'command': 'grep'},
                               tool_response={'llmContent': 'docs say: No such file or directory', 'returnDisplay': ''}))
        self.output(self.event('AfterTool', tool_name='read_file', tool_response={'error': {'message': 'Permission denied'}}))
        lines = (self.data / 'error-log.jsonl').read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])['pattern'], 'file-not-found')

    def test_gemini_only_sync_does_not_enable_other_runtimes(self):
        self.install()
        cli = str(self.home / 'bin/radioheader')
        vault = self.home / 'vault.git'
        self.assertEqual(self.run_cmd('git', 'init', '--bare', str(vault)).returncode, 0)
        r = self.run_cmd(cli, 'device-sync', 'init', '--remote', str(vault))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.home / '.claude/settings.json').exists())
        self.assertFalse((self.home / '.codex/hooks.json').exists())
        for path in ['.gemini-turn-snapshots/test.json', '.gemini-consolidate-counter', '.gemini-consolidate.log', '.gemini-sync.log']:
            self.assertEqual(self.run_cmd('git', 'check-ignore', path, cwd=self.data).returncode, 0, path)
        self.run_cmd(cli, 'index', '--rebuild')
        r = self.run_cmd(cli, 'doctor')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.run_cmd(cli, 'device-sync', 'off').returncode, 0)
        self.assertEqual(self.config_cmd('check').returncode, 0)


if __name__ == '__main__': unittest.main()
