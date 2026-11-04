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
    section('History', '\n'.join('- ' + h['at'] + ': ' + md(h['message']) for h in rec['history']))
    return '\n'.join(lines) + '\n'


def graph(state):
    nodes, edges = {}, []
    for ident, rec in sorted(state['records'].items()):
        nodes[ident] = {'label': ident + ': ' + rec['data']['title'], 'status': rec['status'], 'path': rec['path'], 'kind': 'adr'}
        for ev in rec['evidence']:
            nodes[ev['id']] = {'label': ev['path'], 'status': ev['kind'], 'path': ev['path'], 'kind': 'evidence'}
            edges.append((ev['id'], ident, 'proves'))
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


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.adr-write-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / '.generator.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Generator lock exists. Check for a running writer before removing a stale lock.')
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink()


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


def run(args):
    project = args.project.resolve()
    directory = safe(project, 'docs/adr')
    registry = safe(project, 'docs/adr/registry.json')
    with locked(directory):
        old = read_json(str(registry)) if registry.exists() else {'version': 1, 'records': {}, 'edges': []}
        check(old)
        known = {safe(project, r['path']) for r in old['records'].values()}
        unknown = set(directory.glob('ADR-*.md')) - known
        require(not unknown, 'Unmanaged ADR files found; explicit migration is required: ' + ', '.join(str(p.name) for p in sorted(unknown)))
        if args.command != 'sync' or not args.recover:
            for ident, rec in old['records'].items():
                path = safe(project, rec['path'])
                require(path.is_file() and path.read_text(encoding='utf-8') == render(old, ident), 'Generated ADR edited/missing: ' + ident + '. Restore it or explicitly use sync --recover after checking registry.json.')
        state = deepcopy(old)
        now = stamp()
        result_id = getattr(args, 'id', None)
        def event(rec, message):
            rec['history'].append({'at': now, 'message': message})
        def record(ident):
            require(ident in state['records'], 'Unknown ADR: ' + ident)
            return state['records'][ident]
        if args.command == 'create':
            data = payload(read_json(args.input))
            number = max([int(k[4:]) for k in state['records']] + [0]) + 1
            ident = f'ADR-{number:04}'
            result_id = ident
            slug = args.slug or re.sub(r'[^a-z0-9]+', '-', data['title'].lower()).strip('-')[:70].rstrip('-') or 'decision'
            require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug), 'Invalid slug')
            state['records'][ident] = {'data': data, 'status': 'accepted-for-discussion', 'created': now[:10], 'path': f'docs/adr/{ident}-{slug}.md', 'approval': None, 'approved_hash': None, 'history': [], 'evidence': []}
            event(record(ident), 'Created; accepted-for-discussion.')
        elif args.command == 'update':
            rec = record(args.id)
            require(rec['status'] == 'accepted-for-discussion' and not rec['approval'], 'Approved decisions cannot be rewritten; create a replacement ADR')
            data = payload(read_json(args.input))
            rec['data'] = data
            event(rec, 'Draft content updated: ' + text(args.reason, 'reason'))
        elif args.command == 'link':
            rec = record(args.id)
            record(args.target)
            edge = {'source': args.id, 'target': args.target, 'relation': args.relation}
            require(not rec['approval'] or args.relation == 'extends', 'Approved dependencies are immutable; create a replacement')
            if edge not in state['edges']:
                state['edges'].append(edge)
                event(rec, args.relation + ': ' + args.target)
        elif args.command == 'approve':
            rec = record(args.id)
            require(rec['status'] == 'accepted-for-discussion', 'Only proposals can be approved')
            require(bool(args.replace) == bool(args.rationale), 'Replacement IDs and rationale file are required together')
            rec['approval'] = text(args.approval, 'approval')
            rec['approved_hash'] = digest(dump(rec['data']).encode())
            rec['status'] = 'accepted-for-work'
            event(rec, 'accepted-for-discussion -> accepted-for-work; user approval: ' + rec['approval'])
            for ident in args.replace:
                prior = record(ident)
                require(prior['status'] not in {'superseded', 'rejected'}, 'Cannot replace an already inactive ADR')
                before = prior['status']
                prior['status'] = 'superseded' if prior['approval'] else 'rejected'
                evidence(project, state, prior, args.rationale, 'decision-change-rationale')
                state['edges'].append({'source': args.id, 'target': ident, 'relation': 'replaces'})
                event(prior, before + ' -> ' + prior['status'] + '; replacement approved: ' + args.id + '; new implementation not yet verified.')
        elif args.command == 'complete':
            rec = record(args.id)
            require(rec['status'] == 'accepted-for-work', 'Only approved ADRs can be completed')
            def dependencies_ready(ident):
                return all(record(e['target'])['status'] == 'completed' and dependencies_ready(e['target']) for e in state['edges'] if e['source'] == ident and e['relation'] == 'depends_on')
            require(dependencies_ready(args.id), 'Dependencies must be completed')
            proof = read_json(args.verification)
            keys(proof, ['verified_version', 'architect', 'results'])
            text(proof['verified_version'], 'verified_version')
            text(proof['architect'], 'architect')
            require(isinstance(proof['results'], list), 'results must be a list')
            ids = []
            for row in proof['results']:
                keys(row, ['criterion', 'command', 'result', 'outcome'])
                for k in row:
                    text(row[k], k)
                require(row['outcome'] == 'passed', 'All architect checks must pass')
                ids.append(row['criterion'])
            require(len(ids) == len(set(ids)) and set(ids) == {r['id'] for r in rec['data']['criteria']}, 'Verification must cover every criterion exactly once')
            evidence(project, state, rec, args.evidence, 'verification')
            rec['verification'] = proof
            rec['status'] = 'completed'
            event(rec, 'accepted-for-work -> completed; architect: ' + proof['architect'] + '; verified version: ' + proof['verified_version'])
        check(state)
        # Validate external references before committing state or projections.
        for rec in state['records'].values():
            for ev in rec['evidence']:
                path = safe(project, ev['path'])
                require(path.is_file() and digest(path.read_bytes()) == ev['sha256'], 'Evidence missing or changed: ' + ev['path'])
        projections = {rec['path']: render(state, ident) for ident, rec in state['records'].items()}
        dot, graphml = graph(state)
        projections.update({'docs/adr/graph.dot': dot, 'docs/adr/graph.graphml': graphml})
        # Canonical state commits first. An interrupted projection write is recovered by sync --recover.
        atomic(registry, dump(state))
        for path, content in projections.items():
            atomic(safe(project, path), content)
        return {'records': len(state['records']), 'registry': str(registry), 'graphs': ['docs/adr/graph.dot', 'docs/adr/graph.graphml'], 'adr': result_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('--input', required=True, help='JSON file, or - for stdin')
    create.add_argument('--slug')
    update = sub.add_parser('update')
    update.add_argument('--id', required=True)
    update.add_argument('--input', required=True)
    update.add_argument('--reason', required=True)
    link = sub.add_parser('link')
    link.add_argument('--id', required=True)
    link.add_argument('--relation', choices=['depends_on', 'extends'], required=True)
    link.add_argument('--target', required=True)
    approve = sub.add_parser('approve')
    approve.add_argument('--id', required=True)
    approve.add_argument('--approval', required=True, help='Actual explicit user approval receipt, not an inferred approval')
    approve.add_argument('--replace', action='append', default=[])
    approve.add_argument('--rationale')
    complete = sub.add_parser('complete')
    complete.add_argument('--id', required=True)
    complete.add_argument('--verification', required=True)
    complete.add_argument('--evidence', required=True)
    sync = sub.add_parser('sync')
    sync.add_argument('--recover', action='store_true', help='Explicitly restore generated Markdown from canonical registry after an interrupted write; overwrites projection edits')
    args = parser.parse_args()
    try:
        print(dump(run(args)), end='')
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
