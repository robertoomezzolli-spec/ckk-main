#!/usr/bin/env python3
"""Adapt the existing base/fiber operation to the experimental factor dialect."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ckk_snapshot/ckk/gen'))
import factor_kernel as f
import fiber_kernel as k
spec = importlib.util.spec_from_file_location('factor_runner', ROOT / 'scripts/factor-expansion.py')
factor_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(factor_runner)
SOURCE_HASHES = {name: hashlib.sha256((ROOT / 'ckk_snapshot/ckk/gen' / name).read_bytes()).hexdigest()
                 for name in ('factor_kernel.py', 'fiber_kernel.py')}
VERSION = 'fiber-v1-' + k.digest(SOURCE_HASHES)


def generate(bound, mode, max_nodes=5000, max_events=100000, seconds=30):
    start = time.monotonic()
    initial, factor_report = factor_runner.generate(bound, mode, max_nodes, max_events, seconds)
    if factor_report['termination'] != 'BOUNDED_SATURATION':
        raise ValueError('factor stage must saturate before the Cartesian fiber stage')
    nodes = {n['id']: n['value'] for n in initial['nodes']}
    reached = {i: 0 for i in initial['admitted']}
    events = {}
    for old in initial['events']:
        e = dict(old, version=VERSION)
        e['id'] = k.digest(k.event_identity(e))
        events[e['id']] = e
        reached.setdefault(e['output'], e['level'])

    def record(op, ids, parameters=None, require_existing=False):
        if time.monotonic()-start > seconds:
            raise TimeoutError('TIME_BUDGET')
        out = k.apply(op, [nodes[i] for i in ids], parameters)
        if mode == 'legacy-compatible' and k.legacy_projection(out) is None:
            return
        oid = k.digest(out)
        if require_existing and oid not in nodes:
            raise ValueError('claimed saturated fiber domain is not closed under its operations')
        e = dict(version=VERSION, operator=op, inputs=ids, output=oid,
                 parameters=parameters or {}, level=max(reached[i] for i in ids)+1)
        e['id'] = k.digest(k.event_identity(e))
        if e['id'] in events:
            return
        if len(events) >= max_events:
            raise TimeoutError('EVENT_BUDGET')
        if oid not in nodes and len(nodes) >= max_nodes:
            raise TimeoutError('NODE_BUDGET')
        nodes[oid] = out
        reached.setdefault(oid, e['level'])
        events[e['id']] = e

    termination = 'BOUNDED_SATURATION'
    try:
        bases = [(i, n) for i, n in nodes.items() if n['type'] == 'FACTORS']
        fibers = [(i, n) for i, n in bases if len(n['factors']) == 1]
        for bid, _ in bases:
            for fid, _ in fibers:
                record('fiber', [bid, fid])
        for nid, node in list(nodes.items()):
            if node['type'] != 'FIBER':
                continue
            for op in ('dual_all', 'dual_base', 'dual_fiber'):
                record(op, [nid], require_existing=True)
            for role in ('base', 'fiber'):
                for cls in f.component_classes(node[role]):
                    record('dual_component', [nid], {'role': role, 'class': cls}, require_existing=True)
    except TimeoutError as error:
        termination = str(error)
    graph = dict(version=VERSION, admitted=initial['admitted'],
                 nodes=[{'id': i, 'value': n} for i, n in nodes.items()], events=list(events.values()))
    validation = k.validate_graph(graph, VERSION)
    return graph, dict(mode=mode, base_factor_bound=bound, fiber_factor_count=1,
                       factor_states=len(bases), fiber_states=sum(n['type'] == 'FIBER' for n in nodes.values()),
                       events=len(events), termination=termination, validation=validation)


def backtrace(graph, target):
    parents = {}
    for e in sorted(graph['events'], key=lambda e: e['level']):
        parents.setdefault(e['output'], e)
    wanted, selected = set(graph['admitted']), {}
    def visit(nid):
        if nid in wanted:
            return
        wanted.add(nid)
        e = parents[nid]
        for i in e['inputs']:
            visit(i)
        selected[e['id']] = e
    visit(target)
    result = dict(version=VERSION, admitted=graph['admitted'],
                  nodes=[n for n in graph['nodes'] if n['id'] in wanted],
                  events=sorted(selected.values(), key=lambda e: e['level']))
    k.validate_graph(result, VERSION)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--max-base-factors', type=int, default=3)
    args = p.parse_args()
    old_graph, old = generate(args.max_base_factors, 'legacy-compatible')
    graph, new = generate(args.max_base_factors, 'heterogeneous')
    contained = {n['id'] for n in old_graph['nodes']} <= {n['id'] for n in graph['nodes']}
    if not contained:
        raise ValueError('baseline containment failed')
    a, b = (k.apply('close', [{'type': 'RECURRENCE', 'order': n}]) for n in (2, 3))
    witness = k.apply('fiber', [a, b])
    traces = [{'target': k.digest(n), 'trace': backtrace(graph, k.digest(n))}
              for n in (witness, k.apply('dual_base', [witness]))]
    print(json.dumps(dict(version=VERSION, kernel_sources=SOURCE_HASHES, baseline=old, extension=new,
                         baseline_contained=contained, witnesses=traces,
                         scope='Existing fiber adapted to factor bases and a singleton fiber; no boundary inputs or nested fibers.',
                         interpretation='Ordered structural base/fiber descriptor only; no additional gluing map is represented.',
                         verdict='STRUCTURAL_ADAPTER_VALIDATED'), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
