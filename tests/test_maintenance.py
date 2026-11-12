#!/usr/bin/env python3
"""Regression tests for search integrity, source recovery and runtime boundaries.

Run: python3 -m unittest discover -s tests -p 'test_maintenance.py' -v
All mutations and subprocess HOMEs are isolated under TemporaryDirectory.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unittest
from datetime import datetime
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


INDEX = module(ROOT / 'fts-index.py')
CONSOLIDATE = module(ROOT / 'attn-consolidate.py')


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.data = self.home / '.claude/radioheader'
        (self.data / 'topics').mkdir(parents=True)
        (self.data / 'shortwave').mkdir()
        (self.home / 'bin').mkdir()
        self.env = {**os.environ, 'HOME': str(self.home),
                    'RADIOHEADER_DIR': str(self.data),
                    'PATH': str(self.home / 'bin') + ':' + os.environ['PATH']}
        # Host RadioMind, if installed, must never run in these tests.
        self.stub('radiomind', 'exit 1\n')

    def stub(self, name, body):
        p = self.home / 'bin' / name
        p.write_text('#!/bin/sh\n' + body)
        p.chmod(0o755)
        return p

    def build(self):
        with contextlib.redirect_stdout(io.StringIO()):
            INDEX.build_index(str(self.data), str(self.data / 'search.db'))

    def query(self, term):
        with sqlite3.connect(str(self.data / 'search.db')) as conn:
            conn.execute("INSERT INTO entries_fts(entries_fts, rank) VALUES('integrity-check', 1)")
            return conn.execute('SELECT e.id, e.source, e.body FROM entries_fts '
                                'JOIN entries e ON e.rowid=entries_fts.rowid '
                                'WHERE entries_fts MATCH ?', (term,)).fetchall()

    def sw(self, directory, filename='sw-probe.md', identifier='sw-probe', text='needle'):
        directory.mkdir(parents=True, exist_ok=True)
        p = directory / filename
        p.write_text('---\nid: ' + identifier + '\ndomain: test\ntags: [test]\n---\n# Probe\n' + text)
        return p

    def test_edit_and_delete_sections_remove_old_postings(self):
        p = self.data / 'topics/test.md'
        p.write_text('# Test\n\n## First\noldneedle\n\n## Second\nghostneedle\n')
        self.build()
        p.write_text('# Test\n\n## First\nnewneedle\n')
        self.build()
        self.assertEqual(self.query('oldneedle'), [])
        self.assertEqual(self.query('ghostneedle'), [])
        self.assertEqual(len(self.query('newneedle')), 1)
        p.unlink()
        self.build()
        self.assertEqual(self.query('newneedle'), [])

    def test_local_and_community_same_id_survive(self):
        self.sw(self.data / 'shortwave', text='localneedle')
        remote = self.sw(self.data / 'community/pool', text='remoteneedle')
        self.build()
        self.assertEqual(self.query('localneedle')[0][1], 'shortwave')
        self.assertEqual(self.query('remoteneedle')[0][1], 'community')
        remote.unlink()
        self.build()
        self.assertEqual(len(self.query('localneedle')), 1)

    def test_rename_and_change_id_remove_old_id(self):
        p = self.sw(self.data / 'shortwave')
        self.build()
        p.rename(p.with_name('sw-renamed.md'))
        self.build()
        self.assertEqual(len(self.query('needle')), 1)
        self.sw(self.data / 'shortwave', 'sw-renamed.md', 'sw-new')
        self.build()
        self.assertEqual(self.query('needle')[0][0], 'sw-new')

    def test_registry_mapping_refreshes_unchanged_content(self):
        self.sw(self.data / 'shortwave')
        self.build()
        (self.data / 'project-registry.json').write_text(json.dumps({'domain_index': {'test': ['NewProject']}}))
        self.build()
        with sqlite3.connect(str(self.data / 'search.db')) as conn:
            self.assertEqual(conn.execute('SELECT projects FROM entries').fetchone()[0], 'NewProject')

    def test_old_index_schema_is_rebuilt(self):
        self.sw(self.data / 'shortwave')
        self.build()
        with sqlite3.connect(str(self.data / 'search.db')) as conn:
            conn.execute('PRAGMA user_version=0')
        self.build()
        self.assertEqual(len(self.query('needle')), 1)

    def cli(self, *args):
        return subprocess.run([str(ROOT / 'radioheader'), *args], env=self.env,
                              text=True, capture_output=True, timeout=30)

    def test_corrupt_database_falls_back_to_grep(self):
        (self.data / 'topics/test.md').write_text('# Probe\nneedle fallback evidence\n')
        (self.data / 'search.db').write_bytes(b'not a SQLite database')
        out = self.cli('search', 'needle')
        self.assertEqual(out.returncode, 0, out.stderr + out.stdout)
        self.assertIn('falling back', out.stdout)
        self.assertIn('fallback evidence', out.stdout)

    def test_no_expand_reaches_backend(self):
        self.sw(self.data / 'shortwave', text='blank screen')
        self.build()
        enabled = self.cli('search', '白屏')
        disabled = self.cli('search', '--no-expand', '白屏')
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        self.assertIn('sw-probe', enabled.stdout)
        self.assertNotIn('sw-probe', disabled.stdout)

    def registry(self):
        value = {'projects': [{'name': 'Probe', 'status': 'active', 'search_hits': 0,
                               'path': '/tmp/probe', 'pain_points': ['keep this']}], 'domain_index': {}}
        (self.data / 'project-registry.json').write_text(json.dumps(value))
        return value

    def consolidate(self, dry_run=False):
        with contextlib.redirect_stdout(io.StringIO()):
            CONSOLIDATE.consolidate(str(self.data), dry_run=dry_run)

    def test_consolidate_is_idempotent(self):
        self.registry()
        (self.data / 'search-log.jsonl').write_text(json.dumps({
            'ts': datetime.now().isoformat(), 'hit_projects': ['Probe']}) + '\n')
        self.consolidate()
        self.consolidate()
        data = json.loads((self.data / 'project-registry.json').read_text())
        self.assertEqual(data['projects'][0]['search_hits'], 1)

    def test_missing_registry_recovers_actual_cards(self):
        self.registry()
        self.consolidate()
        (self.data / 'project-registry.json').unlink()
        self.consolidate()
        data = json.loads((self.data / 'project-registry.json').read_text())
        self.assertEqual(data['projects'][0]['pain_points'], ['keep this'])

    def test_missing_source_refuses_empty_replacement(self):
        view = self.data / 'project-registry.md'
        view.write_text('existing project records')
        with self.assertRaisesRegex(ValueError, 'refusing'):
            self.consolidate()
        self.assertFalse((self.data / 'project-registry.json').exists())
        self.assertEqual(view.read_text(), 'existing project records')

    def test_dry_run_writes_nothing_even_when_source_missing(self):
        before = list(self.data.rglob('*'))
        with self.assertRaises(ValueError):
            self.consolidate(dry_run=True)
        self.assertEqual(before, list(self.data.rglob('*')))
        self.registry()
        files = {str(p): p.read_bytes() for p in self.data.rglob('*') if p.is_file()}
        self.consolidate(dry_run=True)
        self.assertEqual(files, {str(p): p.read_bytes() for p in self.data.rglob('*') if p.is_file()})

    def test_both_codex_hooks_find_existing_icloud_memory(self):
        cwd = self.home / 'Library/Mobile Documents/com~apple~CloudDocs/My Project'
        expected = self.home / '.claude/projects' / re.sub(r'[^a-zA-Z0-9_-]', '-', str(cwd.resolve())) / 'memory'
        expected.mkdir(parents=True)
        with patch.dict(os.environ, {'HOME': str(self.home)}):
            for filename in ('radioheader-codex-userprompt.py', 'radioheader-stop-codex.py'):
                hook = module(ROOT / 'templates/hooks' / filename)
                self.assertEqual(hook.project_memory_dir(cwd), expected)

    def test_radioMind_gate_applies_to_real_hook_subprocess(self):
        self.stub('radiomind', 'printf "%s\\n" "$1" >> "$CALL_LOG"\n')
        calls = self.home / 'calls'
        env = {**self.env, 'CALL_LOG': str(calls)}
        project = self.home / 'project'
        project.mkdir()
        for i, (config, override, expected) in enumerate([
                (False, '', False), (True, '0', False), (False, '1', True), (True, '', True)]):
            (self.data / 'config.json').write_text(json.dumps({'radiomind_auto': config}))
            env['RADIOHEADER_RADIOMIND_AUTO'] = override
            payload = json.dumps({'cwd': str(project), 'session_id': 'test', 'turn_id': str(i)})
            if calls.exists():
                calls.unlink()
            for filename in ('radioheader-codex-userprompt.py', 'radioheader-stop-codex.py'):
                if filename.startswith('radioheader-stop'):
                    (self.data / 'topics/test.md').write_text('topic ' + str(i))
                    (self.data / 'shortwave/sw-test.md').write_text('shortwave ' + str(i))
                out = subprocess.run(['python3', str(ROOT / 'templates/hooks' / filename)],
                                     input=payload, text=True, capture_output=True, env=env, timeout=30)
                self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(calls.exists(), expected)

    def test_topic_sources_can_be_inherited_without_inventing_tags(self):
        text = "## [source:Project] Section\n- detail\n## Plain\n[source:Project] Examples:\n\n- example\n## Untagged\n- actual missing source\n```\n- code\n```\n"
        self.assertEqual(INDEX.untagged_topic_lines(text), [8])

    def test_codex_digest_threshold_and_echo_continuation(self):
        calls = self.home / 'digest-calls'
        self.stub('radioheader', 'printf "%s\\n" "$*" >> "$CALL_LOG"\n')
        env = {**self.env, 'CALL_LOG': str(calls), 'RADIOHEADER_RADIOMIND_AUTO': '0'}
        project = self.home / 'project'
        project.mkdir()
        memory = self.home / '.claude/projects' / re.sub(r'[^a-zA-Z0-9_-]', '-', str(project.resolve())) / 'memory'
        memory.mkdir(parents=True)
        def run(name, turn, active=False):
            out = subprocess.run(['python3', str(ROOT / 'templates/hooks' / name)],
                input=json.dumps({'cwd': str(project), 'session_id': 'digest', 'turn_id': str(turn), 'stop_hook_active': active}),
                env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(out.returncode, 0, out.stderr)
            return json.loads(out.stdout) if name.startswith('radioheader-stop') else {}
        counter = self.data / '.codex-consolidate-counter'
        for i in range(5):
            run('radioheader-codex-userprompt.py', i)
            (memory / 'probe.md').write_text('memory change ' + str(i))
            self.assertEqual(run('radioheader-stop-codex.py', i)['decision'], 'block')
            self.assertEqual(int(counter.read_text()), (i + 1) % 5)
            run('radioheader-stop-codex.py', i)
            run('radioheader-stop-codex.py', i, True)
            self.assertEqual(int(counter.read_text()), (i + 1) % 5)
        for _ in range(100):
            if calls.exists():
                break
            time.sleep(.01)
        self.assertEqual(calls.read_text().splitlines(), ['consolidate --native'])
        run('radioheader-codex-userprompt.py', 6)
        run('radioheader-stop-codex.py', 6)
        self.assertEqual(int(counter.read_text()), 0)

    def test_codex_digest_gates_and_invalid_counter(self):
        with patch.dict(os.environ, {'HOME': str(self.home), 'RADIOHEADER_AUTO_DIGEST': '', 'RADIOHEADER_RADIOMIND_AUTO': '0'}):
            hook = module(ROOT / 'templates/hooks/radioheader-stop-codex.py')
            self.assertTrue(hook.auto_digest_enabled())
            (self.data / 'config.json').write_text('{"auto_digest":false}')
            hook.refresh_digest()
            counter = self.data / '.codex-consolidate-counter'
            self.assertFalse(counter.exists())
            (self.data / 'config.json').write_text('{"auto_digest":true}')
            with patch.dict(os.environ, {'RADIOHEADER_AUTO_DIGEST': '0'}):
                hook.refresh_digest()
                self.assertFalse(counter.exists())
            counter.write_text('broken')
            hook.refresh_digest()
            self.assertEqual(int(counter.read_text()), 1)
            counter.write_text('4')
            with patch.object(hook.shutil, 'which', return_value=None):
                hook.refresh_digest()
            self.assertEqual(int(counter.read_text()), 5)
            with patch.object(hook.shutil, 'which', return_value='/test/bin/radioheader'), patch.object(hook.subprocess, 'Popen') as launch:
                hook.refresh_digest()
                self.assertEqual(launch.call_args.args[0], ['/test/bin/radioheader', 'consolidate', '--native'])
                self.assertEqual(int(counter.read_text()), 0)
                counter.write_text('4')
                with patch.dict(os.environ, {'RADIOHEADER_RADIOMIND_AUTO': '1'}):
                    hook.refresh_digest()
                self.assertEqual(launch.call_args.args[0], ['/test/bin/radioheader', 'consolidate'])

    def test_install_reinstall_preserves_unrelated_hooks_and_preferences(self):
        # Start genuinely fresh; installer must target the supplied user bin.
        shutil.rmtree(self.home / '.claude')
        args = ['bash', str(ROOT / 'install.sh'), '--yes', '--bin-dir', str(self.home / 'bin')]
        first = subprocess.run(args, env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        config = self.data / 'config.json'
        config.write_text(json.dumps({'community': True, 'radiomind_auto': False}))
        settings = self.home / '.codex/hooks.json'
        data = json.loads(settings.read_text())
        data['hooks']['Stop'].append({'hooks': [{'type': 'command', 'command': 'custom-hook'}]})
        settings.write_text(json.dumps(data))
        self.registry()
        again = subprocess.run(args, env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertTrue(json.loads(config.read_text())['community'])
        self.assertIn('custom-hook', settings.read_text())
        self.assertEqual(json.loads((self.data / 'project-registry.json').read_text())['projects'][0]['name'], 'Probe')
        self.assertNotIn('/Users/zaptain/', (self.home / '.codex/AGENTS.md').read_text())
        project = self.home / 'Mobile Documents/com~apple~CloudDocs/Test Project'
        project.mkdir(parents=True)
        initialized = subprocess.run([str(self.home / 'bin/radioheader'), 'init', '--runtime', 'both', '--name', 'PathProbe', '--stack', 'Python', '--doc-dir', 'projectBasicInfo'], env=self.env, cwd=project, capture_output=True, text=True, input='', timeout=30)
        self.assertEqual(initialized.returncode, 0, initialized.stdout + initialized.stderr)
        registered = json.loads((self.data / 'project-registry.json').read_text())['projects'][-1]
        self.assertEqual(Path(registered['memory_path']).parent.name,
                         re.sub(r'[^a-zA-Z0-9_-]', '-', str(project.resolve())))


    def test_distributed_templates_have_no_author_home(self):
        for path in (ROOT / 'templates').rglob('*'):
            if path.is_file() and '__pycache__' not in str(path):
                self.assertNotRegex(path.read_text(), r'/Users/[Zz]aptain/')


if __name__ == '__main__':
    unittest.main()
