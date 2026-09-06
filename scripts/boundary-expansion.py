#!/usr/bin/env python3
"""One frontier generator for the experimental product/boundary/fiber path."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ckk_snapshot/ckk/gen'))
import boundary_kernel as k

SOURCES = {name: hashlib.sha256((ROOT / 'ckk_snapshot/ckk/gen' / name).read_bytes()).hexdigest()
           for name in ('factor_kernel.py', 'boundary_kernel.py')}
VERSION = 'boundary-v1-' + k.digest(SOURCES)


def generate(mode, leaves=3, depth=3, max_nodes=5000, max_events=50000, levels=16, seconds=30):
    if mode not in ('legacy-compatible', 'heterogeneous'):
        raise ValueError('invalid mode')
    if any(type(v) is not int for v in (leaves, depth, max_nodes, max_events, levels)) or leaves < 1 or depth < 0 or max_nodes < 4 or max_events < 0 or levels < 1 or seconds <= 0:
        raise ValueError('invalid experiment budget')
    start = time.monotonic()
    seeds = [{'type': 'RECURRENCE', 'order': o} for o in (0, 2, 3, 4)]
    nodes = {k.digest(s): s for s in seeds}
    measures = {i: k.measure(s) for i, s in nodes.items()}
    frontier = list(nodes)
    events, attempted = {}, set()
    blocked = Counter()
    termination = 'LEVEL_BUDGET'
    for level in range(1, levels+1):
        pending = {}

        def record(op, ids, parameters=None):
            if time.monotonic()-start > seconds:
                raise TimeoutError('TIME_BUDGET')
            ids = sorted(ids) if op == 'compose' else ids
            parameters = {} if parameters is None else parameters
            application = (op, tuple(ids), k.canonical(parameters))
            if application in attempted:
                return
            attempted.add(application)
            out = k.apply(op, [nodes[i] for i in ids], parameters)
            m = k.measure(out)
            if m[0] > leaves or m[1] > depth:
                blocked['representation_budget'] += 1
                return
            if mode == 'legacy-compatible' and out['type'] != 'RECURRENCE' and k.legacy_projection(out) is None:
                blocked['legacy_projection'] += 1
                return
            oid = k.digest(out)
            if len(events) >= max_events:
                raise TimeoutError('EVENT_BUDGET')
            if oid not in nodes and oid not in pending:
                if len(nodes)+len(pending) >= max_nodes:
                    raise TimeoutError('NODE_BUDGET')
                pending[oid] = out
                measures[oid] = m
            e = dict(version=VERSION, operator=op, inputs=ids, parameters=parameters,
                     output=oid, level=level)
            e['id'] = k.digest(k.event_identity(e))
            events[e['id']] = e

        try:
            for nid in frontier:
                n = nodes[nid]
                kind = n['type']
                if kind == 'RECURRENCE':
                    record('close', [nid])
                    continue
                record('dual_all', [nid])
                for selector in k.selectors(n):
                    record('dual_component', [nid], selector)
                if kind == 'FIBER':
                    record('dual_base', [nid])
                    record('dual_fiber', [nid])
                if kind == 'FIBER' or kind == 'FACTORS' and len(n['factors']) >= 2:
                    record('boundary', [nid])
            factors = [i for i, n in nodes.items() if n['type'] == 'FACTORS']
            cycles = [i for i in factors if len(nodes[i]['factors']) == 1]
            bases = [i for i, n in nodes.items() if n['type'] in ('FACTORS', 'BOUNDARY')]
            fresh = set(frontier)
            for aid in factors:
                if aid not in fresh:
                    continue
                for bid in factors:
                    if measures[aid][0]+measures[bid][0] <= leaves:
                        record('compose', [aid, bid])
            for bid in bases:
                for fid in cycles:
                    if (bid in fresh or fid in fresh) and measures[bid][0]+1 <= leaves:
                        record('fiber', [bid, fid])
        except TimeoutError as error:
            nodes.update(pending)
            termination = str(error)
            break
        nodes.update(pending)
        frontier = list(pending)
        if not frontier:
            termination = 'BOUNDED_SATURATION'
            break
    graph = dict(version=VERSION, admitted=[k.digest(s) for s in seeds],
                 nodes=[{'id': i, 'value': n} for i, n in nodes.items()], events=list(events.values()))
    validation = k.validate_graph(graph, VERSION)
    projected = Counter(k.canonical(p) for n in nodes.values() if (p := k.legacy_projection(n)) is not None)
    return graph, dict(mode=mode, limits=dict(leaf_occurrences=leaves, constructor_depth=depth,
                     max_nodes=max_nodes, max_events=max_events, levels=levels, seconds=seconds),
                     termination=termination, nodes=len(nodes), events=len(events),
                     kinds=dict(sorted(Counter(n['type'] for n in nodes.values()).items())),
                     zero_rank_relative_nodes=sum(n['type'] in ('BOUNDARY', 'FIBER') and k.dimension(n) == 0 for n in nodes.values()),
                     scalar_projectable_nodes=sum(projected.values()),
                     scalar_projection_classes=len(projected), largest_projection_class=max(projected.values(), default=0),
                     blocked_applications=dict(blocked), validation=validation)


def backtrace(graph, target):
    parents = {}
    for e in sorted(graph['events'], key=lambda e: e['level']):
        parents.setdefault(e['output'], e)
    wanted, selected = set(graph['admitted']), {}
    def visit(nid):
        if nid in wanted:
            return
        wanted.add(nid)
        event = parents[nid]
        for i in event['inputs']:
            visit(i)
        selected[event['id']] = event
    visit(target)
    trace = dict(version=VERSION, admitted=graph['admitted'],
                 nodes=[n for n in graph['nodes'] if n['id'] in wanted],
                 events=sorted(selected.values(), key=lambda e: e['level']))
    k.validate_graph(trace, VERSION)
    return trace


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--leaves', type=int, default=3)
    p.add_argument('--depth', type=int, default=3)
    args = p.parse_args()
    old_graph, old = generate('legacy-compatible', args.leaves, args.depth)
    graph, new = generate('heterogeneous', args.leaves, args.depth)
    old_ids, new_ids = ({n['id'] for n in g['nodes']} for g in (old_graph, graph))
    traces = []
    if args.leaves >= 3 and args.depth >= 3:
        a, b, c = (k.apply('close', [{'type': 'RECURRENCE', 'order': n}]) for n in (2, 3, 4))
        product = k.apply('compose', [a, b])
        boundary = k.apply('boundary', [product])
        fiber = k.apply('fiber', [boundary, c])
        final = k.apply('boundary', [fiber])
        if k.digest(final) in new_ids:
            traces.append({'target': k.digest(final), 'trace': backtrace(graph, k.digest(final))})
    print(json.dumps(dict(version=VERSION, kernel_sources=SOURCES,
                         rule_contract_sha256=hashlib.sha256((ROOT / 'docs/BOUNDARY_ADAPTER_V1.md').read_bytes()).hexdigest(),
                         baseline=old, extension=new, baseline_contained=old_ids <= new_ids,
                         witnesses=traces,
                         interpretation='Relative carrier/rank structures only. Projection collisions and zero-rank incidence growth are reported separately.',
                         scope='Unified close/compose/fiber/boundary/dual subsystem; other legacy operators and domain matching remain outside this run.'),
                     indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
