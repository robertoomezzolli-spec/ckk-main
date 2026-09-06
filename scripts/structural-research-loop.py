#!/usr/bin/env python3
"""Checkpointed, finite expansion experiments over a source-pinned grammar.

External scientific evaluation is a separate unresolved gate. This coordinator
does not change the generator, add seeds, call a model or assert domain matches.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('boundary_runner', ROOT / 'scripts/boundary-expansion.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
k = runner.k
DEFAULT_SCHEDULE = [(2, 2), (3, 3), (3, 4), (3, 5), (4, 5)]


def fingerprint(graph):
    return {'nodes': k.digest(sorted(n['id'] for n in graph['nodes'])),
            'events': k.digest(sorted(e['id'] for e in graph['events']))}


def decision(previous, current, new_states, missing_states):
    if current['termination'] != 'BOUNDED_SATURATION':
        return 'COMPUTE_LIMIT_REACHED'
    if previous is not None and previous['termination'] == 'BOUNDED_SATURATION':
        if missing_states:
            raise ValueError('saturated nested scopes lost previously reachable states')
        if new_states == 0:
            return 'NO_STATE_GROWTH_IN_THIS_SCOPE'
    return 'STRUCTURAL_GROWTH'


def _save(path, value):
    value['checkpoint_hash'] = k.digest({key: item for key, item in value.items() if key != 'checkpoint_hash'})
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
    temp.replace(path)


def run(checkpoint, schedule=None, max_nodes=5000, max_events=50000, seconds=20,
        stop_after=None, progress=False):
    schedule = DEFAULT_SCHEDULE if schedule is None else schedule
    if not schedule or len(schedule) > 20 or any(len(s) != 2 or any(type(v) is not int or v < 1 for v in s) for s in schedule):
        raise ValueError('schedule must contain 1 to 20 positive leaf/depth pairs')
    if any(b[0] < a[0] or b[1] < a[1] for a, b in zip(schedule, schedule[1:])):
        raise ValueError('scheduled scopes must be nested')
    if type(max_nodes) is not int or max_nodes < 4 or type(max_events) is not int or max_events < 0 or seconds <= 0:
        raise ValueError('invalid resource budget')
    if stop_after is not None and (type(stop_after) is not int or stop_after < 0):
        raise ValueError('invalid checkpoint stop index')
    source_paths = ['ckk_snapshot/ckk/gen/factor_kernel.py', 'ckk_snapshot/ckk/gen/boundary_kernel.py',
                    'scripts/boundary-expansion.py', 'scripts/structural-research-loop.py']
    sources = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths}
    protocol = dict(version=runner.VERSION, sources=sources, schedule=[list(s) for s in schedule],
                    max_nodes=max_nodes, max_events=max_events, seconds=seconds)
    protocol_hash = k.digest(protocol)
    checkpoint = Path(checkpoint)
    state = dict(protocol=protocol, protocol_hash=protocol_hash, iterations=[],
                 external_evaluation={'status': 'NOT_RUN', 'reason': 'No executable independent domain fixture is configured for this experimental dialect.'},
                 nature_coverage='NOT_DEFINED', grammar_mutations=0,
                 completion='IN_PROGRESS')
    if checkpoint.exists():
        state = json.loads(checkpoint.read_text())
        if state.get('checkpoint_hash') != k.digest({key: item for key, item in state.items() if key != 'checkpoint_hash'}):
            raise ValueError('checkpoint content hash mismatch')
        if state.get('protocol_hash') != protocol_hash or state.get('protocol') != protocol:
            raise ValueError('checkpoint protocol/source mismatch; use a new experiment checkpoint')
    else:
        _save(checkpoint, state)
    if state['completion'] in ('SCHEDULE_COMPLETED', 'COMPUTE_LIMIT_REACHED'):
        return state
    previous_ids, previous_summary = set(), None
    if state['iterations']:
        last = state['iterations'][-1]
        graph, summary = runner.generate('heterogeneous', leaves=last['scope'][0], depth=last['scope'][1],
                                          max_nodes=max_nodes, max_events=max_events, seconds=seconds)
        if fingerprint(graph) != last['fingerprint']:
            raise ValueError('last checkpoint run did not reproduce exactly')
        previous_ids = {n['id'] for n in graph['nodes']}
        previous_summary = summary
    for index in range(len(state['iterations']), len(schedule)):
        if stop_after is not None and index >= stop_after:
            state['completion'] = 'CHECKPOINTED'
            _save(checkpoint, state)
            return state
        leaves, depth = schedule[index]
        baseline_graph, baseline = runner.generate('legacy-compatible', leaves=leaves, depth=depth,
                                                   max_nodes=max_nodes, max_events=max_events, seconds=seconds)
        graph, summary = runner.generate('heterogeneous', leaves=leaves, depth=depth,
                                         max_nodes=max_nodes, max_events=max_events, seconds=seconds)
        ids = {n['id'] for n in graph['nodes']}
        baseline_ids = {n['id'] for n in baseline_graph['nodes']}
        new_ids, missing = ids-previous_ids, previous_ids-ids
        verdict = decision(previous_summary, summary, len(new_ids), len(missing))
        if summary['termination'] == 'BOUNDED_SATURATION' and not baseline_ids <= ids:
            raise ValueError('saturated extension lost control states')
        sample = min(new_ids, default=None)
        trace = runner.backtrace(graph, sample) if sample else None
        iteration = dict(index=index+1, scope=[leaves, depth], baseline=baseline, result=summary,
                         new_vs_previous_observed=len(new_ids), missing_vs_previous_observed=len(missing),
                         baseline_contained=baseline_ids <= ids, fingerprint=fingerprint(graph),
                         verdict=verdict, sample_target=sample, sample_trace=trace)
        state['iterations'].append(iteration)
        state['completion'] = 'COMPUTE_LIMIT_REACHED' if verdict == 'COMPUTE_LIMIT_REACHED' else 'IN_PROGRESS'
        # Mutating a loaded source during the experiment invalidates the run.
        if any(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h for p, h in sources.items()):
            raise ValueError('source changed during loop')
        _save(checkpoint, state)
        if progress:
            print(json.dumps({'iteration': index+1, 'scope': [leaves, depth], 'nodes': summary['nodes'],
                              'events': summary['events'], 'verdict': verdict}), file=sys.stderr, flush=True)
        if verdict == 'COMPUTE_LIMIT_REACHED':
            break
        previous_ids, previous_summary = ids, summary
    else:
        state['completion'] = 'SCHEDULE_COMPLETED'
    state['next_gate'] = 'Independent external fixtures and interpretation bridge; complete remaining legacy-operator adapters separately.'
    _save(checkpoint, state)
    return state


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--checkpoint', required=True)
    p.add_argument('--max-nodes', type=int, default=5000)
    p.add_argument('--max-events', type=int, default=50000)
    p.add_argument('--seconds-per-run', type=float, default=20)
    args = p.parse_args()
    result = run(args.checkpoint, max_nodes=args.max_nodes, max_events=args.max_events,
                 seconds=args.seconds_per_run, progress=True)
    print(json.dumps({'completion': result['completion'], 'iterations': len(result['iterations']),
                      'external_evaluation': result['external_evaluation']['status'],
                      'checkpoint': str(Path(args.checkpoint))}))


if __name__ == '__main__':
    main()
