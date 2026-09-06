"""Experimental structural factor algebra, version 1.

Identity is a nonempty multiset of scalar CYCLE descriptors, not a derivation
tree. Composition is associative and commutative, but not idempotent. No unit,
factor cancellation, recurrence-order reduction or implicit equivalence exists.
This module has no catalog, domain, database, network or interpretation inputs.
"""
import hashlib
import json

FIELDS = ('kind', 'dim', 'order', 'sym', 'sq', 'anti', 'mult', 'bc', 'dual', 'occ')
CLASS_FIELDS = tuple(f for f in FIELDS if f != 'dual')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def factor(value):
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        raise ValueError('factor must contain exactly the structural fields')
    if value['kind'] != 'CYCLE' or value['dim'] != 1:
        raise ValueError('version 1 admits only dimension-one CYCLE factors')
    if not _integer(value['dim']) or not _integer(value['order']) or not _integer(value['mult'], 1):
        raise ValueError('invalid structural integer')
    if type(value['dual']) is not int or value['dual'] not in (0, 1):
        raise ValueError('invalid dual marker')
    if value['sq'] is not None and (type(value['sq']) is not int or value['sq'] not in (-1, 1)):
        raise ValueError('invalid square')
    if value['anti'] is not None and type(value['anti']) is not bool:
        raise ValueError('invalid anti marker')
    if value['occ'] is not None and (type(value['occ']) is not int or value['occ'] < -1):
        raise ValueError('invalid occupancy')
    for key in ('sym', 'bc'):
        if value[key] is not None and not isinstance(value[key], str):
            raise ValueError('invalid structural marker')
    return dict(value)


def factors(values):
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError('a factor state must be nonempty')
    return {'type': 'FACTORS', 'factors': sorted((factor(v) for v in values), key=canonical)}


def normalize(node):
    if not isinstance(node, dict):
        raise ValueError('node must be an object')
    if set(node) == {'type', 'order'} and node['type'] == 'RECURRENCE' and _integer(node['order']):
        return dict(node)
    if set(node) == {'type', 'factors'} and node['type'] == 'FACTORS':
        return factors(node['factors'])
    raise ValueError('unsupported node fields or type')


def component_class(value):
    value = factor(value)
    return {k: value[k] for k in CLASS_FIELDS}


def component_classes(node):
    node = normalize(node)
    if node['type'] != 'FACTORS':
        raise ValueError('component classes require a factor state')
    return sorted({canonical(component_class(f)): component_class(f)
                   for f in node['factors']}.values(), key=canonical)


def apply(operator, inputs, parameters=None):
    inputs = [normalize(n) for n in inputs]
    parameters = {} if parameters is None else parameters
    if not isinstance(parameters, dict):
        raise ValueError('parameters must be an object')
    arity = {'close': 1, 'compose': 2, 'dual_all': 1, 'dual_component': 1}
    if operator not in arity or len(inputs) != arity[operator]:
        raise ValueError('unknown operator or wrong arity')
    if operator != 'dual_component' and parameters:
        raise ValueError('unexpected parameters')
    if operator == 'close':
        if inputs[0]['type'] != 'RECURRENCE':
            raise ValueError('close requires recurrence')
        return factors([dict(kind='CYCLE', dim=1, order=inputs[0]['order'], sym=None,
                             sq=None, anti=None, mult=1, bc=None, dual=0, occ=None)])
    if any(n['type'] != 'FACTORS' for n in inputs):
        raise ValueError('operator requires factor states')
    if operator == 'compose':
        return factors(inputs[0]['factors'] + inputs[1]['factors'])
    selected = None
    if operator == 'dual_component':
        if set(parameters) != {'class'} or canonical(parameters['class']) not in {
                canonical(c) for c in component_classes(inputs[0])}:
            raise ValueError('component class must be present and exclude the dual marker')
        selected = parameters['class']
    return factors([dict(f, dual=1-f['dual']) if selected is None or component_class(f) == selected
                    else f for f in inputs[0]['factors']])


def legacy_projection(node):
    """Partial, lossy projection; None means no compatible legacy product."""
    node = normalize(node)
    if node['type'] != 'FACTORS':
        return None
    fs = node['factors']
    if len(fs) == 1:
        return dict(fs[0])
    if any(any(f[k] != fs[0][k] for k in ('order', 'sym', 'bc', 'dual')) for f in fs[1:]):
        return None
    return dict(fs[0], kind='PRODUCT', dim=sum(f['dim'] for f in fs), sq=None, anti=None,
                mult=max(f['mult'] for f in fs),
                occ=fs[0]['occ'] if all(f['occ'] == fs[0]['occ'] for f in fs) else None)


def event_identity(event):
    ids = event['inputs']
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ValueError('event inputs must be ids')
    return {'version': event['version'], 'operator': event['operator'],
            'inputs': sorted(ids) if event['operator'] == 'compose' else list(ids),
            'output': event['output'], 'parameters': event['parameters']}


def validate_graph(graph, expected_version, admitted_orders=(0, 2, 3, 4)):
    """Replay complete hyperedges and require all inputs at earlier levels."""
    if graph['version'] != expected_version:
        raise ValueError('unsupported version')
    nodes = {}
    for record in graph['nodes']:
        value = normalize(record['value'])
        if record['id'] != digest(value) or record['id'] in nodes or value != record['value']:
            raise ValueError('invalid, duplicate or noncanonical node')
        nodes[record['id']] = value
    admitted = set(graph['admitted'])
    expected = {digest({'type': 'RECURRENCE', 'order': o}) for o in admitted_orders}
    if admitted != expected or not admitted <= nodes.keys():
        raise ValueError('unadmitted seed set')
    reached = {key: 0 for key in admitted}
    seen = set()
    for event in sorted(graph['events'], key=lambda e: e['level']):
        if event['version'] != expected_version or event['id'] != digest(event_identity(event)):
            raise ValueError('invalid event version or hash')
        if event['id'] in seen:
            raise ValueError('duplicate event')
        seen.add(event['id'])
        level = event['level']
        if not _integer(level, 1) or any(i not in reached or reached[i] >= level for i in event['inputs']):
            raise ValueError('inputs lack earlier seed-rooted derivations')
        output = apply(event['operator'], [nodes[i] for i in event['inputs']], event['parameters'])
        if event['output'] not in nodes or output != nodes[event['output']]:
            raise ValueError('replay output mismatch')
        reached.setdefault(event['output'], level)
    if reached.keys() != nodes.keys():
        raise ValueError('unreachable nodes')
    return {'clean': True, 'replayed_events': len(seen), 'seed_rooted_nodes': len(reached)}
