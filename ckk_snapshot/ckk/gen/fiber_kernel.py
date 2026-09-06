"""Experimental ordered base/fiber structures over the factor-v1 algebra.

A fiber structure retains an ordered base and a singleton fiber. This is a
structural incidence descriptor, not a claim to encode additional gluing data.
Nested fibers and boundary inputs are intentionally outside this version.
"""
import factor_kernel as f

canonical = f.canonical
digest = f.digest


def normalize(node):
    if isinstance(node, dict) and node.get('type') == 'FIBER':
        if set(node) != {'type', 'base', 'fiber'}:
            raise ValueError('unsupported fiber fields')
        base, fiber = f.normalize(node['base']), f.normalize(node['fiber'])
        if base['type'] != 'FACTORS' or fiber['type'] != 'FACTORS' or len(fiber['factors']) != 1:
            raise ValueError('fiber requires factor base and singleton factor fiber')
        return {'type': 'FIBER', 'base': base, 'fiber': fiber}
    return f.normalize(node)


def apply(operator, inputs, parameters=None):
    inputs = [normalize(n) for n in inputs]
    parameters = {} if parameters is None else parameters
    if not isinstance(parameters, dict):
        raise ValueError('parameters must be an object')
    if operator == 'fiber':
        if len(inputs) != 2 or parameters:
            raise ValueError('fiber requires two ordered inputs and no parameters')
        return normalize({'type': 'FIBER', 'base': inputs[0], 'fiber': inputs[1]})
    if operator in ('dual_base', 'dual_fiber'):
        if len(inputs) != 1 or inputs[0]['type'] != 'FIBER' or parameters:
            raise ValueError('role action requires one fiber structure and no parameters')
        role = 'base' if operator == 'dual_base' else 'fiber'
        return normalize(dict(inputs[0], **{role: f.apply('dual_all', [inputs[0][role]])}))
    if operator == 'dual_all' and len(inputs) == 1 and inputs[0]['type'] == 'FIBER':
        if parameters:
            raise ValueError('unexpected parameters')
        return normalize({'type': 'FIBER', **{role: f.apply('dual_all', [inputs[0][role]])
                                            for role in ('base', 'fiber')}})
    if operator == 'dual_component' and len(inputs) == 1 and inputs[0]['type'] == 'FIBER':
        if set(parameters) != {'role', 'class'} or parameters['role'] not in ('base', 'fiber'):
            raise ValueError('component action requires an explicit base/fiber role and class')
        role = parameters['role']
        changed = f.apply('dual_component', [inputs[0][role]], {'class': parameters['class']})
        return normalize(dict(inputs[0], **{role: changed}))
    if any(n['type'] == 'FIBER' for n in inputs):
        raise ValueError('operator is not defined on fiber structures')
    return f.apply(operator, inputs, parameters)


def legacy_projection(node):
    node = normalize(node)
    if node['type'] != 'FIBER':
        return f.legacy_projection(node)
    base, fiber = (f.legacy_projection(node[role]) for role in ('base', 'fiber'))
    if base is None or fiber is None or any(base[k] != fiber[k] for k in ('order', 'sym', 'bc', 'dual')):
        return None
    return dict(base, kind='BUNDLE', sq=None, anti=None, sym=fiber['sym'],
                mult=max(base['mult'], fiber['mult']), occ=fiber['occ'])


def event_identity(event):
    # Only compose is commutative. Reversing fiber inputs changes its identity.
    return f.event_identity(event)


def validate_graph(graph, expected_version):
    if graph['version'] != expected_version:
        raise ValueError('unsupported version')
    nodes = {}
    for record in graph['nodes']:
        value = normalize(record['value'])
        if record['id'] != digest(value) or record['id'] in nodes or value != record['value']:
            raise ValueError('invalid, duplicate or noncanonical node')
        nodes[record['id']] = value
    admitted = set(graph['admitted'])
    expected = {digest({'type': 'RECURRENCE', 'order': o}) for o in (0, 2, 3, 4)}
    if admitted != expected or len(admitted) != len(graph['admitted']) or not admitted <= nodes.keys():
        raise ValueError('unadmitted seed set')
    reached, seen = {i: 0 for i in admitted}, set()
    for event in sorted(graph['events'], key=lambda e: e['level']):
        if event['version'] != expected_version or event['id'] != digest(event_identity(event)):
            raise ValueError('invalid event version or hash')
        if event['id'] in seen:
            raise ValueError('duplicate event')
        seen.add(event['id'])
        level = event['level']
        if not f._integer(level, 1) or any(i not in reached or reached[i] >= level for i in event['inputs']):
            raise ValueError('inputs lack earlier seed-rooted derivations')
        output = apply(event['operator'], [nodes[i] for i in event['inputs']], event['parameters'])
        if event['output'] not in nodes or output != nodes[event['output']]:
            raise ValueError('replay output mismatch')
        reached.setdefault(event['output'], level)
    if reached.keys() != nodes.keys():
        raise ValueError('unreachable nodes')
    return {'clean': True, 'replayed_events': len(seen), 'seed_rooted_nodes': len(reached)}
