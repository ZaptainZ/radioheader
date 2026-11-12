"""Kimi config preservation and lifecycle protocol tests; no network or credentials."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class KimiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rh-kimi-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.kimi = self.home / '.kimi-code'
        self.kimi.mkdir()
        self.config = self.kimi / 'config.toml'
        self.original = '# keep user comment\ndefault_model = "custom-model"\n[[hooks]]\nevent = "Stop"\ncommand = "echo custom"\ntimeout = 30\n\n[services.example]\nurl = "https://example.test"\n'
        self.config.write_text(self.original)
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
        (self.data / 'context-digest.md').write_text('KIMI_DIGEST_PROBE')
        (self.data / 'project-registry.json').write_text('{"projects":[]}')
        (self.data / 'config.json').write_text('{"auto_digest":false}')
        (self.home / 'bin').mkdir()
        self.env = {**os.environ, 'HOME': str(self.home), 'KIMI_CODE_HOME': str(self.kimi),
                    'RADIOHEADER_DIR': str(self.data), 'RADIOHEADER_AUTO_DIGEST': '0',
                    'RADIOHEADER_RADIOMIND_AUTO': '0', 'PATH': str(self.home / 'bin') + ':' + os.environ['PATH']}
        # Never invoke host's optional RadioMind or sync hooks.
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
        return self.run_cmd(sys.executable, str(ROOT / 'kimi-config.py'), action)

    def event(self, event, **extra):
        return self.run_cmd(sys.executable, str(self.hooks / 'radioheader-kimi.py'), event,
                            input=json.dumps(dict(cwd=str(self.project), session_id='../../session', **extra)))

    def install(self, runtime='kimi'):
        r = self.run_cmd('bash', str(ROOT / 'install.sh'), '--yes', '--runtime', runtime, '--bin-dir', str(self.home / 'bin'))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_config_preserves_user_values_and_is_idempotent(self):
        self.assertEqual(self.config_cmd().returncode, 0)
        first = self.config.read_text()
        data = tomllib.loads(first)
        self.assertTrue(first.startswith(self.original.rstrip()))
        self.assertEqual(len(data['hooks']), 6)
        self.assertEqual(data['default_model'], 'custom-model')
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.config_cmd().returncode, 0)
        self.assertEqual(self.config.read_text(), first)
        self.assertEqual(len(list(self.kimi.glob('*.bak.*'))), 1)
        self.assertEqual(self.config_cmd('remove').returncode, 0)
        restored = tomllib.loads(self.config.read_text())
        self.assertEqual(restored, tomllib.loads(self.original))

    def test_reserialized_config_and_unrelated_tables_survive(self):
        self.config_cmd()
        raw = self.config.read_text()
        raw = '\n'.join(x for x in raw.splitlines() if not x.startswith('# --- RadioHeader'))
        self.config.write_text(raw + '\n[models.kept]\nname = "kept"\n')
        self.assertEqual(self.config_cmd().returncode, 0)
        self.assertEqual(len(tomllib.loads(self.config.read_text())['hooks']), 6)
        self.assertEqual(self.config_cmd('remove').returncode, 0)
        data = tomllib.loads(self.config.read_text())
        self.assertEqual(len(data['hooks']), 1)
        self.assertEqual(data['models']['kept']['name'], 'kept')

    def test_bad_toml_and_inline_hooks_preserved(self):
        for raw in ['private = "unfinished', 'hooks = [{event="Stop", command="echo keep"}]\n', '# --- RadioHeader Kimi START ---\n']:
            self.config.write_text(raw)
            r = self.config_cmd()
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(self.config.read_text(), raw)
            self.assertNotIn('unfinished', r.stderr)

    def test_installer_invalid_config_leaves_other_runtimes_untouched(self):
        self.config.write_text('invalid = [')
        r = self.run_cmd('bash', str(ROOT / 'install.sh'), '--yes', '--runtime', 'all', '--bin-dir', str(self.home / 'bin'))
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.home / '.codex/AGENTS.md').exists())
        self.assertFalse((self.home / '.claude/CLAUDE.md').exists())

    def test_install_init_doctor_and_partial_uninstall(self):
        self.install()
        self.assertFalse((self.home / '.claude/settings.json').exists())
        self.assertFalse((self.home / '.codex/hooks.json').exists())
        self.assertEqual(self.config_cmd('check').returncode, 0)
        cli = str(self.home / 'bin/radioheader')
        r = self.run_cmd(cli, 'init', '--runtime', 'kimi', '--name', 'KimiProbe', '--stack', 'Python')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.project / '.kimi-code/AGENTS.md').is_file())
        self.assertFalse((self.project / '.codex/hooks.json').exists())
        self.assertFalse((self.project / 'CLAUDE.md').exists())
        self.assertIn('kimi', self.run_cmd(cli, 'status').stdout.lower())
        self.assertEqual(self.run_cmd(cli, 'index', '--rebuild').returncode, 0)
        r = self.run_cmd(cli, 'doctor')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        entry = self.project / '.kimi-code/AGENTS.md'
        entry.write_text(entry.read_text() + '\nCustom Kimi guidance\n')
        self.assertEqual(self.run_cmd(cli, 'upgrade', 'KimiProbe').returncode, 0)
        self.assertIn('Custom Kimi guidance', entry.read_text())
        entry.unlink()
        self.assertEqual(self.run_cmd(cli, 'upgrade', 'KimiProbe').returncode, 0)
        self.assertTrue(entry.exists())
        self.assertFalse((self.project / 'AGENTS.md').exists())
        r = self.run_cmd('bash', str(ROOT / 'uninstall.sh'), '--runtime', 'kimi')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(tomllib.loads(self.config.read_text()), tomllib.loads(self.original))
        self.assertTrue(Path(cli).exists())
        self.assertTrue((self.hooks / 'radioheader-stop-codex.py').exists())
        self.assertFalse((self.hooks / 'radioheader-kimi.py').exists())

    def test_uninstall_both_preserves_installed_kimi(self):
        self.install('all')
        r = self.run_cmd('bash', str(ROOT / 'uninstall.sh'), '--runtime', 'both', input='n\n')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.config_cmd('check').returncode, 0)
        self.assertTrue((self.home / 'bin/radioheader').exists())
        self.assertTrue((self.hooks / 'radioheader-stop-codex.py').exists())

    def test_prompt_injects_digest_and_steer_preserves_snapshot(self):
        (self.memory / 'MEMORY.md').write_text('PROJECT_MEMORY_PROBE\n' + 'bounded\n' * 205)
        r = self.event('UserPromptSubmit')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('KIMI_DIGEST_PROBE', json.loads(r.stdout)['message'])
        self.assertIn('ARCHITECTURE_PROBE', json.loads(r.stdout)['message'])
        self.assertIn('PROJECT_MEMORY_PROBE', json.loads(r.stdout)['message'])
        self.assertEqual(json.loads(r.stdout)['message'].count('bounded'), 199)
        snapshots = list((self.data / '.kimi-turn-snapshots').glob('*.json'))
        self.assertEqual(len(snapshots), 1)
        before = snapshots[0].read_text()
        (self.memory / 'topic.md').write_text('changed')
        self.assertEqual(self.event('UserPromptSubmit', is_steer=True).stdout, '')
        self.assertEqual(snapshots[0].read_text(), before)
        self.assertFalse((self.data / '.codex-turn-snapshots').exists())

    def test_stop_blocks_once_using_kimi_exit_protocol_and_syncs_on_close(self):
        self.assertEqual(self.event('SessionStart').returncode, 0)
        self.event('UserPromptSubmit')
        (self.memory / 'topic.md').write_text('new lesson')
        r = self.event('Stop')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('global RadioHeader topic', r.stderr)
        self.assertEqual(r.stdout, '')
        self.assertEqual((self.home / 'sync-events').read_text(), 'pull\n')
        self.assertEqual(list((self.data / '.kimi-turn-snapshots').glob('*')), [])
        self.assertEqual(self.event('Stop').returncode, 0)
        self.assertEqual(self.event('SessionEnd').returncode, 0)
        self.assertEqual((self.home / 'sync-events').read_text(), 'pull\npush\npush\n')

    def test_complete_echo_continues_and_counts_kimi_only(self):
        self.env['RADIOHEADER_AUTO_DIGEST'] = '1'
        (self.data / 'config.json').write_text('{}')
        self.stub('radioheader', 'echo "$*" >> "$HOME/consolidated"')
        for i in range(5):
            self.event('UserPromptSubmit')
            for root in [self.memory, self.data / 'topics', self.data / 'shortwave']:
                (root / 'lesson.md').write_text(str(i) * (i + 1))
            r = self.event('Stop')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('message', json.loads(r.stdout))
        deadline = time.monotonic() + 5
        while not (self.home / 'consolidated').exists() and time.monotonic() < deadline: time.sleep(.02)
        self.assertEqual((self.home / 'consolidated').read_text(), 'consolidate --native\n')
        self.assertEqual((self.data / '.kimi-consolidate-counter').read_text().strip(), '0')
        self.assertFalse((self.data / '.codex-consolidate-counter').exists())

    def test_topic_change_requires_shortwave(self):
        self.event('UserPromptSubmit')
        (self.data / 'topics/lesson.md').write_text('new')
        r = self.event('Stop')
        self.assertEqual(r.returncode, 2)
        self.assertIn('shortwave', r.stderr)

    def test_check_detects_missing_engine(self):
        self.install()
        (self.hooks / 'radioheader-stop-codex.py').unlink()
        self.assertNotEqual(self.config_cmd('check').returncode, 0)

    def test_full_uninstall_removes_all_owned_adapters(self):
        self.install('all')
        (self.data / 'topics/keep.md').write_text('user knowledge')
        r = self.run_cmd('bash', str(ROOT / 'uninstall.sh'), '--runtime', 'all', input='n\n')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(tomllib.loads(self.config.read_text()), tomllib.loads(self.original))
        self.assertFalse((self.hooks / 'radioheader-kimi.py').exists())
        self.assertFalse((self.home / 'bin/kimi-config.py').exists())
        self.assertTrue((self.data / 'topics/keep.md').exists())

    def test_custom_hook_inside_managed_markers_is_not_lost(self):
        self.config_cmd()
        raw = self.config.read_text().replace('# --- RadioHeader Kimi END ---', '[[hooks]]\nevent = "Stop"\ncommand = "echo keep-me"\n# --- RadioHeader Kimi END ---')
        self.config.write_text(raw)
        self.assertNotEqual(self.config_cmd().returncode, 0)
        self.assertEqual(self.config.read_text(), raw)

    def test_kimi_only_sync_does_not_enable_other_runtimes(self):
        self.install()
        cli = str(self.home / 'bin/radioheader')
        vault = self.home / 'vault.git'
        self.assertEqual(self.run_cmd('git', 'init', '--bare', str(vault)).returncode, 0)
        r = self.run_cmd(cli, 'device-sync', 'init', '--remote', str(vault))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.home / '.claude/settings.json').exists())
        self.assertFalse((self.home / '.codex/hooks.json').exists())
        for path in ['.kimi-turn-snapshots/test.json', '.kimi-consolidate-counter', '.kimi-consolidate.log']:
            self.assertEqual(self.run_cmd('git', 'check-ignore', path, cwd=self.data).returncode, 0)
        self.run_cmd(cli, 'index', '--rebuild')
        r = self.run_cmd(cli, 'doctor')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.event('SessionStart').returncode, 0)
        self.assertEqual(self.run_cmd(cli, 'device-sync', 'off').returncode, 0)
        self.assertEqual(self.config_cmd('check').returncode, 0)
        # Disabled sync remains inert even though Kimi memory hooks stay installed.
        old = self.run_cmd('git', 'rev-parse', 'HEAD', cwd=self.data).stdout
        (self.data / 'topics/disabled.md').write_text('must not push')
        self.event('SessionEnd')
        self.assertEqual(self.run_cmd('git', 'rev-parse', 'HEAD', cwd=self.data).stdout, old)

    def test_failure_log_is_json_safe(self):
        r = self.event('PostToolUseFailure', tool_name='Bash', error={'message': 'Permission denied "x" \'quote\'\nnext'})
        self.assertEqual(r.returncode, 0, r.stderr)
        record = json.loads((self.data / 'error-log.jsonl').read_text())
        self.assertEqual(record['pattern'], 'permission-denied')
        self.assertIn('quote', record['snippet'])


if __name__ == '__main__': unittest.main()
