"""Run with python3 -m unittest discover -s tests -v from the skill directory."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'adr.py'
BASE = {
    'title': 'Queue "history" <safe>', 'domain': 'documents', 'problem': 'Retries duplicate writes.',
    'solution': 'Use stable request keys.', 'rationale': 'A retry retains its logical identity.',
    'alternatives': [{'option': 'No retries', 'benefits': 'Simple', 'costs': 'Lost work', 'reason': 'Recovery required'}],
    'positive': ['Repeatable writes'], 'negative': ['Key storage required'],
    'triggers': [{'observation': 'Keys exceed storage budget', 'evidence': 'Storage metric', 'reason': 'Reassess retention'}],
    'criteria': [{'id': 'AC-01', 'text': 'A retry produces one external row.'}],
}


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0

    def file(self, value):
        self.counter += 1
        path = self.root / f'input-{self.counter}.json'
        path.write_text(json.dumps(value))
        return str(path)

    def run_cli(self, *args, success=True, raw=False):
        if not raw and args[0] in {'create', 'update', 'import'} and '--author' not in args:
            args = (*args, '--author', 'fixture-architect')
        if not raw and args[0] == 'approve':
            ident = args[args.index('--id') + 1]
            rec = self.state()['records'][ident]
            if not rec.get('reviews'):
                receipt = {'architect': rec.get('author', 'fixture-architect'), 'reviewer': 'fixture-reviewer', 'verdict': 'Approve', 'findings': [], 'walkthroughs': ['Fixture retry and partial-failure walkthrough'], 'limitations': 'Fixture review, not a real project review'}
                self.run_cli('review', '--id', ident, '--input', self.file(receipt), '--evidence', self.evidence('review-' + ident + '.md'), raw=True)
        if not raw and args[0] == 'complete' and '--verification' in args:
            ident = args[args.index('--id') + 1]
            rec = self.state()['records'][ident]
            if rec.get('attempts') and rec['attempts'][-1]['outcome'] != 'passed':
                self.run_cli('authorize-fix', '--id', ident, '--approval', 'Fixture user permission', '--scope', 'Fixture correction', raw=True)
            self.run_cli('verify', '--id', ident, '--verification', args[args.index('--verification') + 1], '--evidence', args[args.index('--evidence') + 1], raw=True)
            args = ('complete', '--id', ident)
        p = subprocess.run([sys.executable, str(SCRIPT), '--project', str(self.root), *args], text=True, capture_output=True)
        self.assertEqual(p.returncode, 0 if success else 2, p.stdout + p.stderr)
        return json.loads(p.stdout if success else p.stderr)

    def create(self, value=None):
        return self.run_cli('create', '--input', self.file(value or BASE))['adr']

    def state(self):
        return json.loads((self.root / 'docs/adr/registry.json').read_text())

    def evidence(self, name):
        path = self.root / 'docs/evidence' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# Evidence\n\nIllustrative fixture only.\n')
        return path.relative_to(self.root).as_posix()

    def proof(self, outcome='passed'):
        return self.file({'verified_version': 'fixture-version', 'architect': 'fixture-architect', 'results': [{'criterion': 'AC-01', 'command': 'fixture-test', 'result': 'one row', 'outcome': outcome}]})

    def test_schema_and_no_overwrite(self):
        invalid = deepcopy(BASE)
        del invalid['problem']
        self.run_cli('create', '--input', self.file(invalid), success=False)
        invalid = {**BASE, 'unexpected': True}
        self.run_cli('create', '--input', self.file(invalid), success=False)
        self.assertFalse((self.root / 'docs/adr/registry.json').exists())
        self.assertEqual(self.create(), 'ADR-0001')
        self.assertEqual(self.create(), 'ADR-0002')

    def test_model_roundtrip_and_markup_escaping(self):
        value = deepcopy(BASE)
        value['problem'] = '# injected heading\n<script>alert()</script> | x'
        value['model'] = {key: 'unknown; measure before approval' for key in ['approach', 'coupling', 'operating_cost', 'switching_cost', 'reopening_observation']}
        ident = self.create(value)
        path = self.root / self.state()['records'][ident]['path']
        self.assertIn('\\# injected', path.read_text())
        self.assertNotIn('<script>', path.read_text())
        before = path.read_bytes()
        self.run_cli('sync')
        self.assertEqual(before, path.read_bytes())

    def test_links_backlinks_cycles_and_graph(self):
        a, b = self.create(), self.create()
        self.run_cli('link', '--id', b, '--relation', 'depends_on', '--target', a)
        before = (self.root / 'docs/adr/registry.json').read_bytes()
        self.run_cli('link', '--id', a, '--relation', 'depends_on', '--target', b, success=False)
        self.assertEqual(before, (self.root / 'docs/adr/registry.json').read_bytes())
        self.run_cli('link', '--id', a, '--relation', 'extends', '--target', 'ADR-9999', success=False)
        for ident, reverse in [(a, 'required_by'), (b, 'depends_on')]:
            self.assertIn(reverse + ': [', (self.root / self.state()['records'][ident]['path']).read_text())
        ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}
        graph = ET.parse(self.root / 'docs/adr/graph.graphml')
        edge = graph.find('.//g:edge', ns)
        self.assertEqual((edge.get('source'), edge.get('target')), (b, a))
        self.assertIn('depends_on', (self.root / 'docs/adr/graph.dot').read_text())
        self.assertEqual(graph.find('.//g:node/g:data[@key="label"]', ns).text, a + ': ' + BASE['title'])

    def test_approval_completion_and_immutability(self):
        a, b = self.create(), self.create()
        self.run_cli('link', '--id', b, '--relation', 'depends_on', '--target', a)
        for ident in [a, b]:
            self.run_cli('approve', '--id', ident, '--approval', 'User explicitly approved fixture version')
        self.run_cli('update', '--id', a, '--input', self.file(BASE), '--reason', 'rewrite', success=False)
        ev = self.evidence('verification.md')
        self.run_cli('complete', '--id', b, '--evidence', ev, '--verification', self.proof(), success=False)
        self.run_cli('complete', '--id', a, '--evidence', ev, '--verification', self.proof('failed'), success=False)
        self.run_cli('complete', '--id', a, '--evidence', ev, '--verification', self.proof())
        self.run_cli('complete', '--id', b, '--evidence', ev, '--verification', self.proof())
        self.assertEqual(self.state()['records'][b]['status'], 'completed')
        graph = ET.parse(self.root / 'docs/adr/graph.graphml')
        adr_nodes = [node for node in graph.findall('.//{*}node') if node.find('{*}data[@key="kind"]').text == 'adr']
        self.assertEqual(len(adr_nodes), 2)

    def test_replacement_preserves_history(self):
        a, draft, new = self.create(), self.create(), self.create()
        self.run_cli('approve', '--id', a, '--approval', 'Approved old')
        self.run_cli('complete', '--id', a, '--evidence', self.evidence('old-proof.md'), '--verification', self.proof())
        self.run_cli('approve', '--id', new, '--approval', 'Approved replacement', '--replace', a, '--replace', draft, '--rationale', self.evidence('replacement.md'))
        state = self.state()
        self.assertEqual(state['records'][a]['status'], 'superseded')
        self.assertEqual(state['records'][draft]['status'], 'rejected')
        self.assertEqual(state['records'][new]['status'], 'accepted-for-work')
        self.assertEqual({e['kind'] for e in state['records'][a]['evidence']}, {'architecture-review', 'verification', 'decision-change-rationale'})
        self.assertIn('completed', json.dumps(state['records'][a]['history']))

    def test_tampering_evidence_and_recovery(self):
        a = self.create()
        path = self.root / self.state()['records'][a]['path']
        expected = path.read_bytes()
        path.write_text('manually edited')
        self.run_cli('sync', success=False)
        self.run_cli('sync', '--recover')
        self.assertEqual(expected, path.read_bytes())
        self.run_cli('approve', '--id', a, '--approval', 'Approved')
        ev = self.evidence('proof.md')
        self.run_cli('complete', '--id', a, '--evidence', ev, '--verification', self.proof())
        (self.root / ev).write_text('rewritten evidence')
        self.run_cli('sync', success=False)

    def test_xml_characters_and_reserved_evidence_url(self):
        invalid = deepcopy(BASE)
        invalid['title'] += '\ufffe'
        self.run_cli('create', '--input', self.file(invalid), success=False)
        self.assertFalse((self.root / 'docs/adr/registry.json').exists())
        ident = self.create()
        self.run_cli('approve', '--id', ident, '--approval', 'Approved')
        ev = self.evidence('check#1?ok%.md')
        self.run_cli('complete', '--id', ident, '--evidence', ev, '--verification', self.proof())
        path = self.root / self.state()['records'][ident]['path']
        self.assertIn('check%231%3Fok%25.md', path.read_text())
        self.assertIn('check%231%3Fok%25.md', (self.root / 'docs/adr/graph.dot').read_text())
        ET.parse(self.root / 'docs/adr/graph.graphml')

    def test_unmanaged_files_paths_and_lock(self):
        folder = self.root / 'docs/adr'
        folder.mkdir(parents=True)
        legacy = folder / 'ADR-0001-legacy.md'
        legacy.write_text('keep history')
        self.run_cli('create', '--input', self.file(BASE), success=False)
        self.assertEqual(legacy.read_text(), 'keep history')
        legacy.unlink()
        lock = folder / '.generator.lock'
        import os
        with lock.open('a+b') as handle:
            if os.name == 'nt':
                import msvcrt
                handle.write(b'0')
                handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.run_cli('create', '--input', self.file(BASE), success=False)
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
        a = self.create()
        self.run_cli('approve', '--id', a, '--approval', 'Approved')
        self.run_cli('verify', '--id', a, '--evidence', '../outside.md', '--verification', self.proof(), success=False, raw=True)


    def test_check_is_read_only_and_detects_stale_graph(self):
        def snapshot():
            return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()}
        before = snapshot()
        self.run_cli('check', raw=True)
        self.assertEqual(before, snapshot())
        self.assertFalse((self.root / 'docs').exists())
        self.create()
        before = snapshot()
        self.run_cli('check', raw=True)
        self.assertEqual(before, snapshot())
        (self.root / 'docs/adr/graph.dot').write_text('stale graph')
        self.run_cli('check', success=False, raw=True)

    def test_review_required_and_bound_to_draft(self):
        ident = self.create()
        self.run_cli('approve', '--id', ident, '--approval', 'User approval', success=False, raw=True)
        receipt = {'architect': 'fixture-architect', 'reviewer': 'fixture-architect', 'verdict': 'Approve', 'findings': [], 'walkthroughs': ['Retry scenario'], 'limitations': 'Fixture'}
        self.run_cli('review', '--id', ident, '--input', self.file(receipt), '--evidence', self.evidence('bad-review.md'), success=False, raw=True)
        receipt['reviewer'] = 'separate-reviewer'
        self.run_cli('review', '--id', ident, '--input', self.file(receipt), '--evidence', self.evidence('good-review.md'), raw=True)
        revised = deepcopy(BASE)
        revised['solution'] = 'Different solution'
        self.run_cli('update', '--id', ident, '--input', self.file(revised), '--reason', 'New investigation')
        self.run_cli('approve', '--id', ident, '--approval', 'User approval', success=False, raw=True)
        self.assertEqual(len(self.state()['records'][ident]['reviews']), 1)

    def test_failed_attempts_preserved_and_permission_required(self):
        ident = self.create()
        self.run_cli('approve', '--id', ident, '--approval', 'Approved')
        proof = self.proof('failed')
        first = self.run_cli('verify', '--id', ident, '--verification', proof, '--evidence', self.evidence('failed-check.md'), raw=True)
        path = self.root / ('docs/evidence/' + first['artifact'] + '.json')
        original = path.read_bytes()
        self.run_cli('complete', '--id', ident, success=False, raw=True)
        self.run_cli('verify', '--id', ident, '--verification', self.proof(), '--evidence', self.evidence('next-check.md'), success=False, raw=True)
        self.run_cli('authorize-fix', '--id', ident, '--approval', 'Actual fixture permission', '--scope', 'Correct fixture implementation', raw=True)
        second = self.run_cli('verify', '--id', ident, '--verification', self.proof(), '--evidence', self.evidence('passed-check.md'), raw=True)
        self.run_cli('complete', '--id', ident, '--attempt', second['artifact'], raw=True)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(len(self.state()['records'][ident]['attempts']), 2)
        self.run_cli('check', raw=True)

    def test_crash_recovery_and_no_duplicate_mutation(self):
        import os
        for variable, exitcode in [('ADR_TEST_INTERRUPT_AFTER_JOURNAL', 93), ('ADR_TEST_INTERRUPT_AFTER_FIRST_WRITE', 94)]:
            with self.subTest(variable=variable):
                # A separate temporary project for each crash point.
                project = self.root / variable
                data = self.file(BASE)
                p = subprocess.run([sys.executable, str(SCRIPT), '--project', str(project), 'create', '--input', data, '--author', 'fixture-architect'], env={**os.environ, variable: '1'}, capture_output=True, text=True)
                self.assertEqual(p.returncode, exitcode, p.stderr)
                journal = project / 'docs/adr/.transaction.json'
                self.assertTrue(journal.exists())
                check = subprocess.run([sys.executable, str(SCRIPT), '--project', str(project), 'check'], capture_output=True, text=True)
                self.assertEqual(check.returncode, 2)
                recovered = subprocess.run([sys.executable, str(SCRIPT), '--project', str(project), 'create', '--input', data, '--author', 'fixture-architect'], capture_output=True, text=True)
                self.assertEqual(recovered.returncode, 0, recovered.stderr)
                self.assertTrue(json.loads(recovered.stdout)['recovered'])
                state = json.loads((project / 'docs/adr/registry.json').read_text())
                self.assertEqual(list(state['records']), ['ADR-0001'])
                self.assertFalse(journal.exists())
                result = subprocess.run([sys.executable, str(SCRIPT), '--project', str(project), 'check'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_import_preserves_source_without_inventing_approval(self):
        source = self.root / 'docs/adr/ADR-0007-legacy.md'
        source.parent.mkdir(parents=True)
        source.write_text('# Historical ADR\n\nStatus: completed\n\nOriginal text\n')
        original = source.read_bytes()
        result = self.run_cli('import', '--id', 'ADR-0007', '--source', 'docs/adr/ADR-0007-legacy.md', '--reported-status', 'completed', '--note', 'Mapped from source; old approval not established', '--input', self.file(BASE))
        rec = self.state()['records']['ADR-0007']
        self.assertEqual(rec['status'], 'accepted-for-discussion')
        self.assertIsNone(rec['approval'])
        self.assertEqual(source.read_bytes(), original)
        self.assertIn('/imported/', rec['path'])
        self.run_cli('check', raw=True)
        index = (self.root / 'docs/adr/INDEX.md').read_text()
        self.assertIn('historical source retained', index)
        self.assertEqual(self.create(), 'ADR-0008')

    def test_baseline_detects_rehashed_approved_content(self):
        ident = self.create()
        self.run_cli('approve', '--id', ident, '--approval', 'Approved')
        def git(*args):
            p = subprocess.run(['git', '-C', str(self.root), *args], text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout.strip()
        git('init')
        git('add', '.')
        git('-c', 'user.name=Fixture User', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Baseline fixture')
        base = git('rev-parse', 'HEAD')
        self.run_cli('check', '--base-ref', base, raw=True)
        import hashlib
        state = self.state()
        state['records'][ident]['data']['solution'] = 'Tampered and rehashed solution'
        data = json.dumps(state['records'][ident]['data'], ensure_ascii=False, indent=2, sort_keys=True) + '\n'
        state['records'][ident]['approved_hash'] = hashlib.sha256(data.encode()).hexdigest()
        (self.root / 'docs/adr/registry.json').write_text(json.dumps(state))
        self.run_cli('sync', '--recover', raw=True)
        self.run_cli('check', '--base-ref', base, success=False, raw=True)

    def test_ci_install_and_unrelated_workflow_preservation(self):
        script = self.root / '.agents/skills/develop-with-adr/scripts/adr.py'
        script.parent.mkdir(parents=True)
        script.write_text('# Fixture project-local script\n')
        self.run_cli('install-ci', raw=True)
        workflow = self.root / '.github/workflows/adr-check.yml'
        self.assertIn('check --base-ref', workflow.read_text())
        self.assertIn('fetch-depth: 0', workflow.read_text())
        self.run_cli('install-ci', raw=True)
        workflow.write_text('unrelated workflow')
        self.run_cli('install-ci', success=False, raw=True)
        self.assertEqual(workflow.read_text(), 'unrelated workflow')


    def test_import_cannot_use_generated_index_as_source(self):
        self.create()
        path = self.root / 'docs/adr/INDEX.md'
        before = path.read_bytes()
        old_state = (self.root / 'docs/adr/registry.json').read_bytes()
        self.run_cli('import', '--id', 'ADR-0002', '--source', 'docs/adr/INDEX.md', '--reported-status', 'historical', '--note', 'Invalid fixture', '--input', self.file(BASE), success=False)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((self.root / 'docs/adr/registry.json').read_bytes(), old_state)
        self.assertFalse((self.root / 'docs/adr/.transaction.json').exists())

    def test_author_change_invalidates_review(self):
        ident = self.create()
        receipt = {'architect': 'fixture-architect', 'reviewer': 'new-author', 'verdict': 'Approve', 'findings': [], 'walkthroughs': ['Failure walkthrough'], 'limitations': 'Fixture'}
        self.run_cli('review', '--id', ident, '--input', self.file(receipt), '--evidence', self.evidence('before-author-change.md'), raw=True)
        self.run_cli('update', '--id', ident, '--input', self.file(BASE), '--reason', 'Author changed', '--author', 'new-author', raw=True)
        self.run_cli('approve', '--id', ident, '--approval', 'Approved', success=False, raw=True)

    def test_baseline_protects_imported_source_descriptor(self):
        import hashlib
        source = self.root / 'legacy.md'
        source.write_text('# Original history\n')
        self.run_cli('import', '--id', 'ADR-0001', '--source', 'legacy.md', '--reported-status', 'accepted', '--note', 'Mapped source', '--input', self.file(BASE))
        def git(*args):
            p = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout.strip()
        git('init')
        git('add', '.')
        git('-c', 'user.name=Fixture User', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Baseline fixture')
        base = git('rev-parse', 'HEAD')
        source.write_text('# Rewritten history\n')
        state = self.state()
        state['records']['ADR-0001']['legacy']['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        (self.root / 'docs/adr/registry.json').write_text(json.dumps(state))
        self.run_cli('sync', '--recover', raw=True)
        self.run_cli('check', '--base-ref', base, success=False, raw=True)


    def test_recovery_does_not_overwrite_intervening_changes(self):
        import os
        data = self.file(BASE)
        crash = subprocess.run([sys.executable, str(SCRIPT), '--project', str(self.root), 'create', '--input', data, '--author', 'fixture-architect'], env={**os.environ, 'ADR_TEST_INTERRUPT_AFTER_FIRST_WRITE': '1'}, capture_output=True, text=True)
        self.assertEqual(crash.returncode, 94)
        document = next((self.root / 'docs/adr').glob('ADR-*.md'))
        document.write_text('Manual intervention after crash')
        self.run_cli('recover', success=False, raw=True)
        self.assertEqual(document.read_text(), 'Manual intervention after crash')
        self.assertTrue((self.root / 'docs/adr/.transaction.json').exists())

    def test_check_rejects_empty_or_missing_registry_with_outputs(self):
        directory = self.root / 'docs/adr'
        directory.mkdir(parents=True)
        registry = directory / 'registry.json'
        registry.write_text('')
        self.run_cli('check', success=False, raw=True)
        registry.unlink()
        (directory / 'graph.dot').write_text('digraph {}')
        self.run_cli('check', success=False, raw=True)


if __name__ == '__main__':
    unittest.main()
