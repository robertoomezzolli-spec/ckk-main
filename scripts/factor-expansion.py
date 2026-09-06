#!/usr/bin/env python3
"""Run a bounded comparison of the product/dual subsystem and emit replayed traces."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ckk_snapshot/ckk/gen'))
import factor_kernel as k

VERSION = 'factor-v1-' + hashlib.sha256(Path(k.__file__).read_bytes()).hexdigest()


def generate(bound, mode, max_nodes=5000, max_events=100000, seconds=30):
    if type(bound) is not int or bound < 1 or mode not in ('legacy-compatible', 'heterogeneous'):
        raise ValueError('invalid experiment bounds or mode')
    if type(max_nodes) is not int or max_nodes < 4 or type(max_events) is not int or max_events < 0 or seconds <= 0:
        raise ValueError('invalid resource budget')
    start = time.monotonic()
    seeds = [{'type': 'RECURRENCE', 'order': o} for o in (0, 2, 3, 4)]
    nodes = {k.digest(n): n for n in seeds}
    events = {}
    termination = 'LEVEL_BUDGET'
    for level in range(1, 17):
        pending = {}
        items = list(nodes.items())

        def record(op, ids, parameters=None):
            nonlocal termination
            if time.monotonic()-start > seconds:
                termination = 'TIME_BUDGET'
                raise TimeoutError(termination)
            out = k.apply(op, [nodes[i] for i in ids], parameters)
            if out['type'] == 'FACTORS' and len(out['factors']) > bound:
                return
            if mode == 'legacy-compatible' and out['type'] == 'FACTORS' and k.legacy_projection(out) is None:
                return
            oid = k.digest(out)
            e = dict(version=VERSION, operator=op, inputs=sorted(ids) if op == 'compose' else ids,
                     output=oid, parameters=parameters or {}, level=level)
            e['id'] = k.digest(k.event_identity(e))
            if e['id'] in events:
                return
            if len(events) >= max_events:
                termination = 'EVENT_BUDGET'
                raise TimeoutError(termination)
            if oid not in nodes and oid not in pending:
                if len(nodes) + len(pending) >= max_nodes:
                    termination = 'NODE_BUDGET'
                    raise TimeoutError(termination)
                pending[oid] = out
            events[e['id']] = e

        try:
            for nid, node in items:
                if node['type'] == 'RECURRENCE':
                    record('close', [nid])
                else:
                    record('dual_all', [nid])
                    for cls in k.component_classes(node):
                        record('dual_component', [nid], {'class': cls})
            fs = [(nid, n) for nid, n in items if n['type'] == 'FACTORS']
            for i, (aid, a) in enumerate(fs):
                for bid, b in fs[i:]:
                    if len(a['factors']) + len(b['factors']) <= bound:
                        record('compose', [aid, bid])
        except TimeoutError:
            nodes.update(pending)
            break
        nodes.update(pending)
        if not pending:
            termination = 'BOUNDED_SATURATION'
            break
    graph = dict(version=VERSION, admitted=[k.digest(s) for s in seeds],
                 nodes=[{'id': i, 'value': n} for i, n in nodes.items()], events=list(events.values()))
    validation = k.validate_graph(graph, VERSION)
    return graph, dict(mode=mode, factor_bound=bound, termination=termination,
                       factor_states=len(nodes)-len(seeds), events=len(events), validation=validation)


def backtrace(graph, target):
    parents = {}
    for e in sorted(graph['events'], key=lambda e: e['level']):
        parents.setdefault(e['output'], e)
    wanted = set(graph['admitted'])
    selected = {}

    def visit(nid):
        if nid in wanted:
            return
        wanted.add(nid)
        e = parents[nid]
        for i in e['inputs']:
            visit(i)
        selected[e['id']] = e

    visit(target)
    trace = dict(version=graph['version'], admitted=graph['admitted'],
                 nodes=[n for n in graph['nodes'] if n['id'] in wanted],
                 events=sorted(selected.values(), key=lambda e: e['level']))
    k.validate_graph(trace, VERSION)
    return trace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-factors', type=int, default=4)
    args = parser.parse_args()
    baseline, old = generate(args.max_factors, 'legacy-compatible')
    graph, new = generate(args.max_factors, 'heterogeneous')
    old_ids = {n['id'] for n in baseline['nodes']}
    new_ids = {n['id'] for n in graph['nodes']}
    if not old_ids <= new_ids:
        raise ValueError('baseline containment failed')
    traces = []
    for node in graph['nodes']:
        v = node['value']
        if v['type'] == 'FACTORS' and len(v['factors']) == 2:
            if sorted((f['order'], f['dual']) for f in v['factors']) in (
                    [(2, 0), (3, 0)], [(2, 1), (3, 0)], [(2, 0), (2, 1)]):
                traces.append({'target': node['id'], 'trace': backtrace(graph, node['id'])})
    fixed = [n['id'] for n in graph['nodes'] if n['value']['type'] == 'FACTORS'
             and k.apply('dual_all', [n['value']]) == n['value']]
    print(json.dumps(dict(version=VERSION, baseline=old, extension=new,
                         baseline_contained=True, additional_factor_states=len(new_ids-old_ids),
                         global_dual_fixed_states=len(fixed),
                         fixed_point_meaning='Exact equality under the explicitly chosen factor-multiset equivalence only; no external interpretation or legacy dual=2 state.',
                         witnesses=traces,
                         scope='Reduced recurrence/close/product/dual subsystem, not the full 11-operator fan.',
                         assumptions=['Associative commutative non-idempotent factor composition.',
                                      'Factor-class duality toggles all copies in a class defined without dual.',
                                      'No new recurrence orders, dimension limit in the algebra, or recurrence reduction.',
                                      'Factor count is a runner budget only; saturation is relative to it.'],
                         verdict='STRUCTURAL_EXTENSION_ONLY'), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
