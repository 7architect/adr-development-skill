#!/usr/bin/env python3
"""Deterministic ADR records, Markdown projections, and DOT/GraphML graphs (stdlib only)."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from urllib.parse import quote as urlquote

STATUSES = {'accepted-for-discussion', 'accepted-for-work', 'completed', 'rejected', 'superseded'}
REVERSE = {'depends_on': 'required_by', 'extends': 'extended_by', 'replaces': 'replaced_by'}
NS = 'http://graphml.graphdrawing.org/xmlns'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, label):
    require(isinstance(value, str) and value.strip() and not any(ord(c) < 32 and c not in '\n\t' for c in value), f'{label}: expected nonempty text without control characters')
    require(all(ord(c) in (9, 10, 13) or 0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF for c in value), f'{label}: invalid XML 1.0 character')
    return value.strip()


def keys(value, required, optional=()):
    require(isinstance(value, dict), 'Expected a JSON object')
    require(set(required) <= value.keys(), f'Missing keys: {sorted(set(required) - value.keys())}')
    require(not (value.keys() - set(required) - set(optional)), f'Unknown keys: {sorted(value.keys() - set(required) - set(optional))}')


def payload(value):
    required = ['title', 'domain', 'problem', 'solution', 'rationale', 'alternatives', 'positive', 'negative', 'triggers', 'criteria']
    keys(value, required, ['no_alternatives', 'model'])
    result = deepcopy(value)
    for key in ['title', 'domain', 'problem', 'solution', 'rationale']:
        result[key] = text(value[key], key)
    for key in ['positive', 'negative']:
        require(isinstance(value[key], list) and value[key], f'{key}: nonempty list required')
        result[key] = [text(v, key) for v in value[key]]
    rows = {'alternatives': ['option', 'benefits', 'costs', 'reason'], 'triggers': ['observation', 'evidence', 'reason'], 'criteria': ['id', 'text']}
    for key, fields in rows.items():
        require(isinstance(value[key], list), f'{key}: list required')
        require(value[key] or key == 'alternatives', f'{key}: cannot be empty')
        result[key] = []
        for row in value[key]:
            keys(row, fields)
            result[key].append({k: text(row[k], key + '.' + k) for k in fields})
    if not result['alternatives']:
        result['no_alternatives'] = text(value.get('no_alternatives'), 'no_alternatives')
    else:
        require('no_alternatives' not in value, 'Use alternatives or no_alternatives, not both')
    ids = [v['id'] for v in result['criteria']]
    require(len(ids) == len(set(ids)) and all(re.fullmatch(r'AC-[0-9]{2,}', v) for v in ids), 'Criteria need unique stable IDs such as AC-01')
    if 'model' in value:
        fields = ['approach', 'coupling', 'operating_cost', 'switching_cost', 'reopening_observation']
        keys(value['model'], fields)
        result['model'] = {k: text(value['model'][k], 'model.' + k) for k in fields}
    return result


def read_json(path):
    raw = sys.stdin.read() if path == '-' else Path(path).read_text(encoding='utf-8')
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, 'Duplicate JSON key: ' + key)
            obj[key] = value
        return obj
    return json.loads(raw, object_pairs_hook=unique)


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def md(value):
    # Plain text arguments cannot inject Markdown headings, links, HTML or table cells.
    return re.sub(r'([\\`*_{}\[\]<>#+.!|~-])', r'\\\1', str(value)).replace('\n', ' ')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(md(x) for x in row) + ' |' for row in rows])


def relative(source, target):
    return urlquote(Path(os.path.relpath(target, Path(source).parent)).as_posix(), safe='/')


def relations(state, ident):
    found = []
    for edge in state['edges']:
        if edge['source'] == ident:
            found.append((edge['relation'], edge['target']))
        if edge['target'] == ident:
            found.append((REVERSE[edge['relation']], edge['source']))
    return sorted(found)


def render(state, ident):
    rec = state['records'][ident]
    data = rec['data']
    lines = ['---', 'id: ' + ident, 'status: ' + rec['status'], 'domain: ' + json.dumps(data['domain'], ensure_ascii=False), 'created: ' + rec['created'], 'generator: develop-with-adr/v1', '---', '', '# ' + ident + ': ' + md(data['title'])]
    if rec.get('author'):
        lines[5:5] = ['author: ' + json.dumps(rec['author'], ensure_ascii=False), 'revision: ' + str(rec.get('revision', 0))]
    def section(title, content):
        lines.extend(['', '## ' + title, '', content])
    for title, key in [('Problem', 'problem'), ('Proposed solution', 'solution'), ('Rationale', 'rationale')]:
        section(title, md(data[key]))
    section('Alternatives considered', table(['Alternative', 'Benefits', 'Costs / limitations', 'Reason not selected'], [[r[k] for k in ['option', 'benefits', 'costs', 'reason']] for r in data['alternatives']]) if data['alternatives'] else md(data['no_alternatives']))
    section('Consequences', '### Positive\n\n' + '\n'.join('- ' + md(v) for v in data['positive']) + '\n\n### Negative\n\n' + '\n'.join('- ' + md(v) for v in data['negative']))
    section('Reconsideration triggers', table(['Observation / threshold', 'Evidence source', 'Why to reconsider'], [[r[k] for k in ['observation', 'evidence', 'reason']] for r in data['triggers']]))
    if 'model' in data:
        section('Model choice', table(['Aspect', 'Decision and basis'], [[k.replace('_', ' ').capitalize(), v] for k, v in [(name, data['model'][name]) for name in ['approach', 'coupling', 'operating_cost', 'switching_cost', 'reopening_observation']]]))
    section('Acceptance criteria', '\n'.join('- ' + r['id'] + ': ' + md(r['text']) for r in data['criteria']))
    links = []
    for name in ['replaces', 'replaced_by', 'depends_on', 'required_by', 'extends', 'extended_by', 'evidence']:
        targets = [(target, state['records'][target]['path']) for relation, target in relations(state, ident) if relation == name]
        if name == 'evidence':
            targets = [(e['id'], e['path']) for e in rec['evidence']]
        links.append('- ' + name + ': ' + (', '.join('[' + target + '](' + relative(rec['path'], path) + ')' for target, path in targets) or '[]'))
    section('Relationships', '\n'.join(links))
    section('Approval', (md(rec['approval']) + '\n\nApproved content SHA-256: `' + rec['approved_hash'] + '`') if rec['approval'] else 'Not received.')
    if rec.get('legacy'):
        source = rec['legacy']
        section('Imported source', '[' + md(source['source_path']) + '](' + relative(rec['path'], source['source_path']) + ')\n\nReported historical status: ' + md(source['reported_status']) + '. Imported as an unapproved proposal; historical approval or completion has not been established.\n\nSource SHA-256: `' + source['source_sha256'] + '`')
    for heading, key in [('Architecture reviews', 'reviews'), ('Verification attempts', 'attempts')]:
        if rec.get(key):
            section(heading, '\n'.join('- [' + item['id'] + '](' + relative(rec['path'], item['path']) + '): ' + md(item.get('verdict', item.get('outcome', 'recorded'))) for item in rec[key]))
    section('History', '\n'.join('- ' + h['at'] + ': ' + md(h['message']) for h in rec['history']))
    return '\n'.join(lines) + '\n'


def graph(state):
    nodes, edges = {}, []
    for ident, rec in sorted(state['records'].items()):
        nodes[ident] = {'label': ident + ': ' + rec['data']['title'], 'status': rec['status'], 'path': rec['path'], 'kind': 'adr'}
        for ev in rec['evidence']:
            nodes[ev['id']] = {'label': ev['path'], 'status': ev['kind'], 'path': ev['path'], 'kind': 'evidence'}
            edges.append((ev['id'], ident, 'proves'))
        for field in ['reviews', 'attempts']:
            for item in rec.get(field, []):
                nodes[item['id']] = {'label': item['id'], 'status': item.get('verdict', item.get('outcome', 'recorded')), 'path': item['path'], 'kind': field}
                edges.append((item['id'], ident, 'reviews' if field == 'reviews' else 'verifies'))
        if rec.get('legacy'):
            source = rec['legacy']
            source_id = 'SOURCE-' + digest(source['source_path'].encode())[:16]
            nodes[source_id] = {'label': source['source_path'], 'status': source['reported_status'], 'path': source['source_path'], 'kind': 'legacy-source'}
            edges.append((source_id, ident, 'imported_as'))
    edges.extend((e['source'], e['target'], e['relation']) for e in state['edges'])
    edges = sorted(set(edges))
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    dot = ['digraph ADR {', '  rankdir=TB;', '  node [shape=box];']
    for ident, node in sorted(nodes.items()):
        label = node['label'] + '\n' + node['status']
        dot.append('  ' + quote(ident) + ' [label=' + quote(label) + ', URL=' + quote(relative('docs/adr/graph.dot', node['path'])) + '];')
    for a, b, kind in edges:
        dot.append('  ' + quote(a) + ' -> ' + quote(b) + ' [label=' + quote(kind) + '];')
    dot.append('}')
    ET.register_namespace('', NS)
    yns = 'http://www.yworks.com/xml/graphml'
    ET.register_namespace('y', yns)
    ytag = lambda name: '{' + yns + '}' + name
    tag = lambda value: '{' + NS + '}' + value
    root = ET.Element(tag('graphml'))
    for key in ['label', 'status', 'path', 'kind', 'relation']:
        ET.SubElement(root, tag('key'), {'id': key, 'for': 'all', 'attr.name': key, 'attr.type': 'string'})
    ET.SubElement(root, tag('key'), {'id': 'graphics', 'for': 'node', 'yfiles.type': 'nodegraphics'})
    ET.SubElement(root, tag('key'), {'id': 'edgegraphics', 'for': 'edge', 'yfiles.type': 'edgegraphics'})
    g = ET.SubElement(root, tag('graph'), {'id': 'ADR', 'edgedefault': 'directed'})
    for ident, node in sorted(nodes.items()):
        n = ET.SubElement(g, tag('node'), {'id': ident})
        for k, value in node.items():
            ET.SubElement(n, tag('data'), {'key': k}).text = value
        visual = ET.SubElement(ET.SubElement(n, tag('data'), {'key': 'graphics'}), ytag('ShapeNode'))
        ET.SubElement(visual, ytag('Geometry'), {'x': '0.0', 'y': '0.0', 'width': '320.0', 'height': '70.0'})
        ET.SubElement(visual, ytag('NodeLabel')).text = node['label'] + '\n' + node['status']
        ET.SubElement(visual, ytag('Shape'), {'type': 'rectangle'})
    for index, (a, b, kind) in enumerate(edges):
        edge = ET.SubElement(g, tag('edge'), {'id': 'edge-' + str(index), 'source': a, 'target': b})
        ET.SubElement(edge, tag('data'), {'key': 'relation'}).text = kind
        visual = ET.SubElement(ET.SubElement(edge, tag('data'), {'key': 'edgegraphics'}), ytag('PolyLineEdge'))
        ET.SubElement(visual, ytag('Arrows'), {'source': 'none', 'target': 'standard'})
        ET.SubElement(visual, ytag('EdgeLabel')).text = kind
    ET.indent(root)
    xml = ET.tostring(root, encoding='unicode', xml_declaration=True) + '\n'
    return '\n'.join(dot) + '\n', xml


def check(state):
    keys(state, ['version', 'records', 'edges'])
    require(isinstance(state['records'], dict) and isinstance(state['edges'], list), 'Invalid registry collections')
    require(state.get('version') == 1, 'Unsupported registry version')
    for ident, rec in state['records'].items():
        require(re.fullmatch(r'ADR-[0-9]{4,}', ident), 'Invalid ADR ID')
        require(rec['status'] in STATUSES, 'Invalid status')
        payload(rec['data'])
        if rec.get('approved_hash'):
            require(rec['approved_hash'] == digest(dump(rec['data']).encode()), 'Approved decision content changed: ' + ident)
    for relation in REVERSE:
        adjacency = {key: [] for key in state['records']}
        for e in state['edges']:
            require(e['relation'] in REVERSE and e['source'] in adjacency and e['target'] in adjacency, 'Unknown relationship or missing target')
            require(e['source'] != e['target'], 'Self links are forbidden')
            if e['relation'] == relation:
                adjacency[e['source']].append(e['target'])
        if relation in {'depends_on', 'replaces'}:
            visiting, done = set(), set()
            def visit(node):
                require(node not in visiting, 'Cycle in ' + relation)
                if node in done:
                    return
                visiting.add(node)
                for target in adjacency[node]:
                    visit(target)
                visiting.remove(node)
                done.add(node)
            for node in adjacency:
                visit(node)

    require(isinstance(state['records'], dict) and isinstance(state['edges'], list), 'Invalid registry collections')
    require(len({int(k[4:]) for k in state['records']}) == len(state['records']), 'Duplicate numeric ADR ID')
    paths = set()
    for ident, rec in state['records'].items():
        require(re.fullmatch(r'docs/adr/(?:imported/)?ADR-[0-9]{4,}-[a-z0-9-]+\.md', rec['path']), 'Invalid generated ADR path')
        require(rec['path'] not in paths, 'Duplicate ADR path')
        paths.add(rec['path'])
        require(isinstance(rec['history'], list) and rec['history'], 'Missing history')
        for event in rec['history']:
            keys(event, ['at', 'message'])
            text(event['at'], 'history timestamp')
            text(event['message'], 'history message')
        require(isinstance(rec['evidence'], list), 'Invalid evidence collection')
        for item in rec['evidence']:
            keys(item, ['id', 'path', 'kind', 'sha256'])
            require(re.fullmatch(r'[a-f0-9]{64}', item['sha256']), 'Invalid evidence checksum')
            text(item['path'], 'evidence path')
        for field in ['reviews', 'attempts']:
            require(isinstance(rec.get(field, []), list), 'Invalid artifact collection')
            for index, item in enumerate(rec.get(field, []), 1):
                prefix = 'REVIEW' if field == 'reviews' else 'ATTEMPT'
                expected = f'{prefix}-{ident}-{index:04}'
                require(item['id'] == expected and item['path'] == f'docs/evidence/{expected}.json', 'Invalid artifact identity or path')
                require(any(ev['id'] == item['evidence'] for ev in rec['evidence']), 'Artifact evidence reference missing')
                if field == 'reviews':
                    review_receipt(item['receipt'])
                    require(item['verdict'] == item['receipt']['verdict'], 'Review verdict mismatch')
                else:
                    passed = verification(item['receipt'], rec)
                    require(item['outcome'] == ('passed' if passed else 'failed'), 'Attempt outcome mismatch')
        if rec.get('approval'):
            require(rec.get('approved_hash'), 'Approval needs a content fingerprint')
            if rec.get('governance_version') == 2:
                reviews = [item for item in rec.get('reviews', []) if item['id'] == rec.get('approved_review')]
                require(len(reviews) == 1 and reviews[0]['verdict'] == 'Approve' and reviews[0]['proposal_hash'] == rec.get('approved_proposal_hash'), 'Approval lacks an independent review')
                require(reviews[0]['receipt']['architect'] == rec.get('author') and reviews[0]['receipt']['reviewer'] != rec.get('author'), 'Approved review does not match the proposal author')
        if rec['status'] in {'accepted-for-work', 'completed', 'superseded'}:
            require(rec.get('approval'), 'Approved status lacks an approval receipt')
        if rec['status'] == 'completed':
            require(rec.get('verification') and verification(rec['verification'], rec), 'Completion lacks all-passing verification')
            if rec.get('governance_version') == 2:
                require(rec.get('attempts') and rec['completed_attempt'] == rec['attempts'][-1]['id'] and rec['attempts'][-1]['outcome'] == 'passed', 'Completion must reference the latest passing attempt')
        if rec['status'] in {'rejected', 'superseded'}:
            replacements = [e['source'] for e in state['edges'] if e['target'] == ident and e['relation'] == 'replaces']
            require(replacements and all(state['records'][key].get('approval') for key in replacements), 'Inactive ADR lacks an approved replacement')
            require(any(ev['kind'] in {'decision-change-rationale', 'rejection-rationale'} for ev in rec['evidence']), 'Inactive ADR lacks change rationale')


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.adr-write-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        if os.name != 'nt':
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked(directory, readonly=False):
    # Advisory locks release automatically when a process exits, including crashes.
    path = directory / '.generator.lock'
    if readonly and not path.exists():
        yield
        return
    if not readonly:
        directory.mkdir(parents=True, exist_ok=True)
    with path.open('rb' if readonly else 'a+b') as handle:
        try:
            if os.name == 'nt':
                import msvcrt
                if not readonly and path.stat().st_size == 0:
                    handle.write(b'0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBRLCK if readonly else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, (fcntl.LOCK_SH if readonly else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except OSError:
            raise ValueError('Another generator is running; retry after it finishes')
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def safe(project, value):
    path = (project / value).resolve()
    require(path.is_relative_to(project), 'Path must stay inside the project: ' + str(value))
    return path


def evidence(project, state, rec, path, kind):
    file = safe(project, path)
    require(file.is_file() and file.suffix == '.md', 'Evidence must be an existing Markdown document')
    rel = file.relative_to(project).as_posix()
    text(rel, 'evidence path')
    require(rel.startswith('docs/evidence/'), 'Evidence must be in docs/evidence/')
    require(' ' not in rel and not any(c in rel for c in '()[]\n'), 'Evidence path must be Markdown-safe')
    ident = 'EVID-' + digest(rel.encode())[:16]
    item = {'id': ident, 'path': rel, 'kind': kind, 'sha256': digest(file.read_bytes())}
    rec['evidence'].append(item)
    return item


def proposal_hash(state, ident):
    return digest(dump({'author': state['records'][ident].get('author'), 'revision': state['records'][ident].get('revision', 0), 'data': state['records'][ident]['data'], 'links': sorted((e for e in state['edges'] if e['source'] == ident and e['relation'] != 'replaces'), key=lambda e: (e['relation'], e['target']))}).encode())


def verification(proof, rec):
    keys(proof, ['verified_version', 'architect', 'results'])
    text(proof['verified_version'], 'verified_version')
    text(proof['architect'], 'architect')
    require(isinstance(proof['results'], list), 'results must be a list')
    ids = []
    for row in proof['results']:
        keys(row, ['criterion', 'command', 'result', 'outcome'])
        for key in row:
            text(row[key], key)
        require(row['outcome'] in {'passed', 'failed', 'blocked', 'not-verified'}, 'Invalid verification outcome')
        ids.append(row['criterion'])
    require(len(ids) == len(set(ids)) and set(ids) == {r['id'] for r in rec['data']['criteria']}, 'Verification must cover every criterion exactly once')
    return all(row['outcome'] == 'passed' for row in proof['results'])


def artifact(rec, field, content, now):
    items = rec.setdefault(field, [])
    prefix = 'REVIEW' if field == 'reviews' else 'ATTEMPT'
    ident = f'{prefix}-{rec["id"]}-{len(items) + 1:04}'
    item = {'id': ident, 'path': f'docs/evidence/{ident}.json', 'at': now, **content}
    items.append(item)
    return item


def review_receipt(value):
    keys(value, ['architect', 'reviewer', 'verdict', 'findings', 'walkthroughs', 'limitations'])
    for key in ['architect', 'reviewer', 'limitations']:
        text(value[key], key)
    require(value['architect'] != value['reviewer'], 'Reviewer must be separate from the proposal architect')
    require(value['verdict'] in {'Approve', 'Request changes', 'Blocked'}, 'Invalid review verdict')
    require(isinstance(value['findings'], list), 'findings must be a list')
    for finding in value['findings']:
        keys(finding, ['severity', 'location', 'problem', 'impact', 'evidence', 'correction'])
        for key, val in finding.items():
            text(val, key)
        require(finding['severity'] in {'blocker', 'important'}, 'Invalid finding severity')
    require(value['verdict'] != 'Approve' or not value['findings'], 'Cannot approve with unresolved findings')
    require(isinstance(value['walkthroughs'], list) and value['walkthroughs'], 'At least one concrete failure/request walkthrough is required')
    for case in value['walkthroughs']:
        text(case, 'walkthrough')
    return value


def index(state):
    lines = ['# ADR decision index', '', 'Generated from registry.json. Read before selecting governing ADRs. Approval and implementation are distinct.', '']
    rows = []
    for ident, rec in sorted(state['records'].items()):
        blockers = [e['target'] for e in state['edges'] if e['source'] == ident and e['relation'] == 'depends_on' and state['records'][e['target']]['status'] != 'completed']
        replacements = [source for relation, source in relations(state, ident) if relation == 'replaced_by']
        pending = [key for key in replacements if state['records'][key]['status'] != 'completed']
        note = ('Blocked by ' + ', '.join(blockers)) if blockers else ''
        if pending:
            note += '; replacement not verified: ' + ', '.join(pending)
        if rec.get('legacy'):
            note += '; historical source retained; reported status: ' + rec['legacy']['reported_status']
        governing = rec['status'] in {'accepted-for-work', 'completed'}
        rows.append('| [' + ident + '](' + relative('docs/adr/INDEX.md', rec['path']) + ') | ' + md(rec['data']['title']) + ' | ' + rec['status'] + ' | ' + ('yes' if governing else 'no') + ' | ' + ('yes' if rec['status'] == 'completed' else 'no') + ' | ' + md(note.strip('; ')) + ' |')
    lines.extend(['| ADR | Decision | Status | Approved current scope | Implementation verified | Notes |', '| --- | --- | --- | --- | --- | --- |', *rows])
    return '\n'.join(lines) + '\n'


def projections(state):
    result = {rec['path']: render(state, ident) for ident, rec in state['records'].items()}
    dot, xml = graph(state)
    result.update({'docs/adr/graph.dot': dot, 'docs/adr/graph.graphml': xml, 'docs/adr/INDEX.md': index(state)})
    for rec in state['records'].values():
        for field in ['reviews', 'attempts']:
            for item in rec.get(field, []):
                require(item['path'] not in result, 'Artifact path collision')
                result[item['path']] = dump(item)
    return result


def validate_external(project, state):
    generated = {safe(project, path) for path in projections(state)}
    for rec in state['records'].values():
        for ev in rec['evidence']:
            path = safe(project, ev['path'])
            require(path.is_file() and digest(path.read_bytes()) == ev['sha256'], 'Evidence missing or changed: ' + ev['path'])
        if rec.get('legacy'):
            source = rec['legacy']
            path = safe(project, source['source_path'])
            require(path not in generated, 'Historical source overlaps generated output: ' + source['source_path'])
            require(path.is_file() and digest(path.read_bytes()) == source['source_sha256'], 'Historical source missing or changed: ' + source['source_path'])


def unmanaged(project, state):
    known = {safe(project, r['path']) for r in state['records'].values()}
    known.update(safe(project, r['legacy']['source_path']) for r in state['records'].values() if r.get('legacy'))
    return set(safe(project, 'docs/adr').glob('ADR-*.md')) - known


def baseline(project, state, ref):
    if not ref or set(ref) == {'0'}:
        return
    # An arbitrary string cannot become an option or a shell expression.
    resolved = subprocess.run(['git', '-C', str(project), 'rev-parse', '--verify', ref + '^{commit}'], capture_output=True, text=True)
    require(resolved.returncode == 0, 'Cannot resolve baseline Git commit')
    sha = resolved.stdout.strip()
    exists = subprocess.run(['git', '-C', str(project), 'ls-tree', sha, '--', 'docs/adr/registry.json'], capture_output=True, text=True)
    require(exists.returncode == 0, 'Cannot inspect baseline tree')
    if not exists.stdout.strip():
        return
    result = subprocess.run(['git', '-C', str(project), 'show', sha + ':docs/adr/registry.json'], capture_output=True, text=True)
    require(result.returncode == 0, 'Cannot read baseline registry')
    previous = json.loads(result.stdout)
    check(previous)
    for ident, old in previous['records'].items():
        require(ident in state['records'], 'ADR deleted since baseline: ' + ident)
        new = state['records'][ident]
        allowed = {'accepted-for-discussion': STATUSES, 'accepted-for-work': {'accepted-for-work', 'completed', 'superseded'}, 'completed': {'completed', 'superseded'}, 'superseded': {'superseded'}, 'rejected': {'rejected'}}
        require(new['status'] in allowed[old['status']], 'Invalid status regression: ' + ident)
        if old.get('legacy'):
            require(new.get('legacy') == old['legacy'], 'Imported source descriptor rewritten: ' + ident)
        require(new['history'][:len(old['history'])] == old['history'], 'History rewritten: ' + ident)
        for field in ['reviews', 'attempts', 'corrections', 'evidence']:
            require(new.get(field, [])[:len(old.get(field, []))] == old.get(field, []), field + ' history rewritten: ' + ident)
        if old.get('approved_hash'):
            require(new['data'] == old['data'] and new.get('approval') == old.get('approval') and new.get('approved_hash') == old['approved_hash'], 'Approved decision rewritten since baseline: ' + ident)
            for field in ['author', 'approved_review', 'approved_proposal_hash']:
                require(new.get(field) == old.get(field), 'Approved metadata rewritten: ' + ident)
            old_deps = [e for e in previous['edges'] if e['source'] == ident and e['relation'] == 'depends_on']
            new_deps = [e for e in state['edges'] if e['source'] == ident and e['relation'] == 'depends_on']
            require(old_deps == new_deps, 'Approved dependencies changed since baseline: ' + ident)
    for edge in previous['edges']:
        require(edge in state['edges'], 'Historical relationship deleted')


def durable_remove(path):
    path.unlink()
    if os.name != 'nt':
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def recover_pending(project):
    journal = safe(project, 'docs/adr/.transaction.json')
    if not journal.exists():
        return False
    txn = read_json(str(journal))
    keys(txn, ['base', 'target', 'state', 'before', 'writes'])
    check(txn['state'])
    validate_external(project, txn['state'])
    require(txn['writes'] == projections(txn['state']), 'Journal projections do not match target state')
    require(digest(dump(txn['state']).encode()) == txn['target'], 'Journal target checksum mismatch')
    registry = safe(project, 'docs/adr/registry.json')
    current = digest(registry.read_bytes()) if registry.exists() else None
    require(current in {txn['base'], txn['target']}, 'Registry changed after pending transaction')
    require(set(txn['before']) == set(txn['writes']), 'Invalid journal before-images')
    for name, content in txn['writes'].items():
        path = safe(project, name)
        actual = digest(path.read_bytes()) if path.exists() else None
        require(actual in {txn['before'][name], digest(content.encode())}, 'File changed after interruption: ' + name)
    for name, content in txn['writes'].items():
        atomic(safe(project, name), content)
    atomic(registry, dump(txn['state']))
    durable_remove(journal)
    return True


def commit(project, old, state, allow_recover=False):
    check(state)
    validate_external(project, state)
    output = projections(state)
    before = {}
    previous = projections(old)
    for name, content in output.items():
        path = safe(project, name)
        raw = path.read_bytes() if path.exists() else None
        before[name] = digest(raw) if raw is not None else None
        if name not in previous:
            require(raw is None or raw == content.encode(), 'Refusing to overwrite unrelated file: ' + name)
        elif not allow_recover:
            # New index/graph projections are initialized by sync, not silently overwritten.
            require(raw is None or raw == previous[name].encode(), 'Generated file edited: ' + name)
    registry = safe(project, 'docs/adr/registry.json')
    txn = {'base': digest(registry.read_bytes()) if registry.exists() else None, 'target': digest(dump(state).encode()), 'state': state, 'before': before, 'writes': output}
    journal = safe(project, 'docs/adr/.transaction.json')
    atomic(journal, dump(txn))
    if os.environ.get('ADR_TEST_INTERRUPT_AFTER_JOURNAL') == '1':
        # Deterministic process-crash fixture. Never set in normal operation.
        os._exit(93)
    for offset, (name, content) in enumerate(output.items()):
        atomic(safe(project, name), content)
        if offset == 0 and os.environ.get('ADR_TEST_INTERRUPT_AFTER_FIRST_WRITE') == '1':
            os._exit(94)
    atomic(registry, dump(state))
    durable_remove(journal)


def check_project(args):
    project = args.project.resolve()
    directory = safe(project, 'docs/adr')
    with locked(directory, readonly=True):
        journal = safe(project, 'docs/adr/.transaction.json')
        require(not journal.exists(), 'Interrupted transaction pending; run recover')
        registry = safe(project, 'docs/adr/registry.json')
        raw = registry.read_bytes() if registry.exists() else None
        state = read_json(str(registry)) if raw is not None else {'version': 1, 'records': {}, 'edges': []}
        check(state)
        require(not unmanaged(project, state), 'Unmanaged legacy ADRs need import')
        validate_external(project, state)
        if raw is None:
            require(not any(safe(project, name).exists() for name in ['docs/adr/INDEX.md', 'docs/adr/graph.dot', 'docs/adr/graph.graphml']), 'Generated graph/index exists without registry')
        if raw is not None:
            for name, content in projections(state).items():
                path = safe(project, name)
                require(path.is_file() and path.read_bytes() == content.encode(), 'Generated file missing or stale: ' + name)
        baseline(project, state, args.base_ref)
        require((registry.read_bytes() if registry.exists() else None) == raw and not journal.exists(), 'Concurrent change during read-only check; retry')
        return {'valid': True, 'records': len(state['records']), 'baseline': args.base_ref, 'readonly': True}


def workflow(script):
    require(re.fullmatch(r'[A-Za-z0-9_./-]+', script), 'CI script path must be shell-safe')
    return '''name: ADR integrity
on: [push, pull_request]
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Check ADR state and immutable history
        env:
          ADR_SCRIPT: SCRIPT_PLACEHOLDER
          ADR_BASE_REF: ${{ github.event.pull_request.base.sha || github.event.before }}
        run: python3 "$ADR_SCRIPT" --project . check --base-ref "$ADR_BASE_REF"
'''.replace('SCRIPT_PLACEHOLDER', script)


def run(args):
    project = args.project.resolve()
    if args.command == 'check':
        return check_project(args)
    if args.command == 'install-ci':
        require(safe(project, args.script_path).is_file(), 'CI needs a project-local copy of the generator; commit it and its support files')
        path = safe(project, '.github/workflows/adr-check.yml')
        content = workflow(args.script_path)
        require(not path.exists() or path.read_text() == content, 'Existing CI workflow differs; refusing to overwrite it')
        atomic(path, content)
        return {'workflow': str(path), 'script': args.script_path}
    directory = safe(project, 'docs/adr')
    registry = safe(project, 'docs/adr/registry.json')
    with locked(directory):
        if recover_pending(project):
            return {'recovered': True, 'requested_command_not_applied': args.command, 'message': 'Pending operation completed. Inspect state before issuing another mutation.'}
        if args.command == 'recover':
            return {'recovered': False, 'message': 'No pending operation.'}
        old = read_json(str(registry)) if registry.exists() else {'version': 1, 'records': {}, 'edges': []}
        check(old)
        unknown = unmanaged(project, old)
        require(not unknown or args.command == 'import', 'Unmanaged ADR files found; use import: ' + ', '.join(str(p.name) for p in sorted(unknown)))
        if args.command != 'sync' or not args.recover:
            for ident, rec in old['records'].items():
                path = safe(project, rec['path'])
                require(path.is_file() and path.read_text(encoding='utf-8') == render(old, ident), 'Generated ADR edited/missing: ' + ident + '. Inspect state before sync --recover.')
        state = deepcopy(old)
        now = stamp()
        result_id = getattr(args, 'id', None)
        artifact_id = None
        def event(rec, message):
            rec['history'].append({'at': now, 'message': message})
        def record(ident):
            require(ident in state['records'], 'Unknown ADR: ' + ident)
            return state['records'][ident]
        if args.command in {'create', 'import'}:
            data = payload(read_json(args.input))
            number = max([int(k[4:]) for k in state['records']] + [0]) + 1
            ident = args.id if args.command == 'import' else f'ADR-{number:04}'
            require(re.fullmatch(r'ADR-[0-9]{4,}', ident), 'ID must be ADR-0001 or longer')
            require(ident not in state['records'] and int(ident[4:]) not in {int(k[4:]) for k in state['records']}, 'ADR ID already exists')
            result_id = ident
            slug = args.slug or re.sub(r'[^a-z0-9]+', '-', data['title'].lower()).strip('-')[:70].rstrip('-') or 'decision'
            require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug), 'Invalid slug')
            rec = {'id': ident, 'governance_version': 2, 'revision': 1, 'author': text(args.author, 'author'), 'data': data, 'status': 'accepted-for-discussion', 'created': now[:10], 'path': f'docs/adr/{ident}-{slug}.md', 'approval': None, 'approved_hash': None, 'history': [], 'evidence': [], 'reviews': [], 'attempts': [], 'corrections': []}
            if args.command == 'import':
                source = safe(project, args.source)
                require(source.is_file() and source.suffix == '.md', 'Import source must be an existing project Markdown file')
                source_path = source.relative_to(project).as_posix()
                text(source_path, 'source path')
                require(not any(r.get('legacy', {}).get('source_path') == source_path or r['path'] == source_path for r in state['records'].values()), 'Source is already managed or imported')
                rec['path'] = f'docs/adr/imported/{ident}-{slug}.md'
                rec['legacy'] = {'source_path': source_path, 'source_sha256': digest(source.read_bytes()), 'reported_status': text(args.reported_status, 'reported_status'), 'mapping_note': text(args.note, 'mapping_note')}
            state['records'][ident] = rec
            event(rec, 'Imported source retained without historical approval/completion claims; accepted-for-discussion.' if args.command == 'import' else 'Created; accepted-for-discussion.')
        elif args.command == 'update':
            rec = record(args.id)
            require(rec['status'] == 'accepted-for-discussion' and not rec['approval'], 'Approved decisions cannot be rewritten; create a replacement ADR')
            rec['data'] = payload(read_json(args.input))
            rec['author'] = text(args.author, 'author')
            rec['revision'] = rec.get('revision', 0) + 1
            event(rec, 'Draft updated; prior reviews are stale: ' + text(args.reason, 'reason'))
        elif args.command == 'link':
            rec = record(args.id)
            record(args.target)
            edge = {'source': args.id, 'target': args.target, 'relation': args.relation}
            require(not rec['approval'] or args.relation == 'extends', 'Approved dependencies are immutable; create a replacement')
            if edge not in state['edges']:
                state['edges'].append(edge)
                event(rec, args.relation + ': ' + args.target)
        elif args.command == 'review':
            rec = record(args.id)
            require(rec['status'] == 'accepted-for-discussion', 'Review the proposal before user approval')
            receipt = review_receipt(read_json(args.input))
            require(not rec.get('author') or receipt['architect'] == rec['author'], 'Review architect does not match current proposal author')
            rec.setdefault('id', args.id)
            ev = evidence(project, state, rec, args.evidence, 'architecture-review')
            item = artifact(rec, 'reviews', {'proposal_hash': proposal_hash(state, args.id), 'receipt': receipt, 'verdict': receipt['verdict'], 'evidence': ev['id']}, now)
            artifact_id = item['id']
            event(rec, 'Independent architecture review: ' + item['id'] + '; ' + receipt['verdict'])
        elif args.command == 'approve':
            rec = record(args.id)
            require(rec['status'] == 'accepted-for-discussion', 'Only proposals can be approved')
            review = rec.get('reviews', [])[-1] if rec.get('reviews') else None
            require(review and review['verdict'] == 'Approve' and review['proposal_hash'] == proposal_hash(state, args.id), 'A current independent Approve review is required')
            require(bool(args.replace) == bool(args.rationale), 'Replacement IDs and rationale file are required together')
            rec['approval'] = text(args.approval, 'approval')
            rec['approved_hash'] = digest(dump(rec['data']).encode())
            rec['approved_review'] = review['id']
            rec['approved_proposal_hash'] = review['proposal_hash']
            rec['status'] = 'accepted-for-work'
            event(rec, 'accepted-for-discussion -> accepted-for-work; user approval: ' + rec['approval'])
            for ident in args.replace:
                prior = record(ident)
                require(prior['status'] not in {'superseded', 'rejected'}, 'Cannot replace an already inactive ADR')
                before = prior['status']
                prior['status'] = 'superseded' if prior['approval'] else 'rejected'
                evidence(project, state, prior, args.rationale, 'decision-change-rationale')
                state['edges'].append({'source': args.id, 'target': ident, 'relation': 'replaces'})
                event(prior, before + ' -> ' + prior['status'] + '; replacement approved: ' + args.id + '; implementation not yet verified.')
        elif args.command == 'authorize-fix':
            rec = record(args.id)
            require(rec['status'] == 'accepted-for-work' and rec.get('attempts') and rec['attempts'][-1]['outcome'] != 'passed', 'Correction permission needs a failed or blocked latest attempt')
            permission = {'attempt': rec['attempts'][-1]['id'], 'at': now, 'approval': text(args.approval, 'approval'), 'scope': text(args.scope, 'scope')}
            rec.setdefault('corrections', []).append(permission)
            event(rec, 'User authorized correction for ' + permission['attempt'] + ': ' + permission['scope'])
        elif args.command == 'verify':
            rec = record(args.id)
            require(rec['status'] == 'accepted-for-work', 'Verification needs an approved implementation')
            previous = rec.get('attempts', [])[-1] if rec.get('attempts') else None
            if previous and previous['outcome'] != 'passed':
                require(any(p['attempt'] == previous['id'] for p in rec.get('corrections', [])), 'Actual user permission for this correction cycle is required')
            proof = read_json(args.verification)
            passed = verification(proof, rec)
            rec.setdefault('id', args.id)
            ev = evidence(project, state, rec, args.evidence, 'verification')
            item = artifact(rec, 'attempts', {'receipt': proof, 'outcome': 'passed' if passed else 'failed', 'evidence': ev['id']}, now)
            artifact_id = item['id']
            event(rec, 'Verification attempt recorded: ' + item['id'] + '; ' + item['outcome'])
        elif args.command == 'complete':
            rec = record(args.id)
            require(rec['status'] == 'accepted-for-work', 'Only approved ADRs can be completed')
            def dependencies_ready(ident):
                return all(record(e['target'])['status'] == 'completed' and dependencies_ready(e['target']) for e in state['edges'] if e['source'] == ident and e['relation'] == 'depends_on')
            require(dependencies_ready(args.id), 'Dependencies must be completed')
            require(rec.get('attempts'), 'Record verification using verify first')
            attempt = rec['attempts'][-1]
            require(not args.attempt or attempt['id'] == args.attempt, 'Completion must use the latest attempt')
            require(attempt['outcome'] == 'passed' and verification(attempt['receipt'], rec), 'The latest attempt must pass every criterion')
            rec['verification'] = attempt['receipt']
            rec['completed_attempt'] = attempt['id']
            rec['status'] = 'completed'
            event(rec, 'accepted-for-work -> completed; ' + attempt['id'] + '; verified version: ' + attempt['receipt']['verified_version'])
        commit(project, old, state, allow_recover=args.command == 'sync' and args.recover)
        return {'records': len(state['records']), 'registry': str(registry), 'graphs': ['docs/adr/graph.dot', 'docs/adr/graph.graphml'], 'index': 'docs/adr/INDEX.md', 'adr': result_id, 'artifact': artifact_id, 'outcome': item.get('outcome', item.get('verdict')) if args.command in {'review', 'verify'} else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ['create', 'import']:
        create = sub.add_parser(command)
        create.add_argument('--input', required=True, help='JSON file, or - for stdin')
        create.add_argument('--slug')
        create.add_argument('--author', required=True, help='Actual architect agent identifier')
        if command == 'import':
            create.add_argument('--id', required=True)
            create.add_argument('--source', required=True)
            create.add_argument('--reported-status', required=True)
            create.add_argument('--note', required=True, help='Mapping basis; does not assert historical approval')
    update = sub.add_parser('update')
    update.add_argument('--id', required=True)
    update.add_argument('--input', required=True)
    update.add_argument('--author', required=True)
    update.add_argument('--reason', required=True)
    link = sub.add_parser('link')
    link.add_argument('--id', required=True)
    link.add_argument('--relation', choices=['depends_on', 'extends'], required=True)
    link.add_argument('--target', required=True)
    review = sub.add_parser('review')
    review.add_argument('--id', required=True)
    review.add_argument('--input', required=True)
    review.add_argument('--evidence', required=True)
    approve = sub.add_parser('approve')
    approve.add_argument('--id', required=True)
    approve.add_argument('--approval', required=True)
    approve.add_argument('--replace', action='append', default=[])
    approve.add_argument('--rationale')
    verify = sub.add_parser('verify')
    verify.add_argument('--id', required=True)
    verify.add_argument('--verification', required=True)
    verify.add_argument('--evidence', required=True)
    fix = sub.add_parser('authorize-fix')
    fix.add_argument('--id', required=True)
    fix.add_argument('--approval', required=True)
    fix.add_argument('--scope', required=True)
    complete = sub.add_parser('complete')
    complete.add_argument('--id', required=True)
    complete.add_argument('--attempt')
    sync = sub.add_parser('sync')
    sync.add_argument('--recover', action='store_true', help='Explicitly restore generated projections from the checked registry')
    sub.add_parser('recover')
    checker = sub.add_parser('check')
    checker.add_argument('--base-ref', default='')
    ci = sub.add_parser('install-ci')
    ci.add_argument('--script-path', default='.agents/skills/develop-with-adr/scripts/adr.py')
    args = parser.parse_args()
    try:
        print(dump(run(args)), end='')
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
