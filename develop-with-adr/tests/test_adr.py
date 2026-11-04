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

    def run_cli(self, *args, success=True):
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
        self.assertEqual(len(graph.findall('.//{*}node')), 3)

    def test_replacement_preserves_history(self):
        a, draft, new = self.create(), self.create(), self.create()
        self.run_cli('approve', '--id', a, '--approval', 'Approved old')
        self.run_cli('complete', '--id', a, '--evidence', self.evidence('old-proof.md'), '--verification', self.proof())
        self.run_cli('approve', '--id', new, '--approval', 'Approved replacement', '--replace', a, '--replace', draft, '--rationale', self.evidence('replacement.md'))
        state = self.state()
        self.assertEqual(state['records'][a]['status'], 'superseded')
        self.assertEqual(state['records'][draft]['status'], 'rejected')
        self.assertEqual(state['records'][new]['status'], 'accepted-for-work')
        self.assertEqual(len(state['records'][a]['evidence']), 2)
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
        lock.write_text('fixture')
        self.run_cli('create', '--input', self.file(BASE), success=False)
        lock.unlink()
        a = self.create()
        self.run_cli('approve', '--id', a, '--approval', 'Approved')
        self.run_cli('complete', '--id', a, '--evidence', '../outside.md', '--verification', self.proof(), success=False)


if __name__ == '__main__':
    unittest.main()
