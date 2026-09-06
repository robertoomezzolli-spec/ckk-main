"""Relative carrier/rank descriptors over the existing factor and fiber dialects."""
import factor_kernel as f

canonical = f.canonical
digest = f.digest
event_identity = f.event_identity


def _dimension(node):
    if node['type'] == 'FACTORS':
        return len(node['factors'])
    if node['type'] == 'FIBER':
        return _dimension(node['base'])
    if node['type'] == 'BOUNDARY':
        return node['rank']
    return 0


def normalize(node):
    if not isinstance(node, dict):
        raise ValueError('node must be an object')
    kind = node.get('type')
    if kind == 'FIBER':
        if set(node) != {'type', 'base', 'fiber'}:
            raise ValueError('unsupported fiber fields')
        base, fiber = normalize(node['base']), f.normalize(node['fiber'])
        if base['type'] not in ('FACTORS', 'BOUNDARY') or fiber['type'] != 'FACTORS' or len(fiber['factors']) != 1:
            raise ValueError('invalid base/fiber roles')
        return {'type': 'FIBER', 'base': base, 'fiber': fiber}
    if kind == 'BOUNDARY':
        if set(node) != {'type', 'carrier', 'rank'}:
            raise ValueError('unsupported boundary fields')
        carrier = normalize(node['carrier'])
        if not (carrier['type'] == 'FIBER' or carrier['type'] == 'FACTORS' and len(carrier['factors']) >= 2):
            raise ValueError('boundary requires product or fiber carrier')
        if not f._integer(node['rank']) or node['rank'] != max(_dimension(carrier)-1, 0):
            raise ValueError('boundary rank does not follow its carrier')
        return {'type': 'BOUNDARY', 'carrier': carrier, 'rank': node['rank']}
    return f.normalize(node)


def dimension(node):
    return _dimension(normalize(node))


def measure(node):
    """Return leaf occurrences and constructor depth, for runner budgets only."""
    node = normalize(node)
    if node['type'] == 'RECURRENCE':
        return 0, 0
    if node['type'] == 'FACTORS':
        return len(node['factors']), 0
    if node['type'] == 'BOUNDARY':
        count, depth = measure(node['carrier'])
        return count, depth+1
    a, b = measure(node['base']), measure(node['fiber'])
    return a[0]+b[0], max(a[1], b[1])+1


def selectors(node):
    node = normalize(node)
    if node['type'] == 'RECURRENCE':
        return []
    if node['type'] == 'FACTORS':
        return [{'path': [], 'class': cls} for cls in f.component_classes(node)]
    roles = ('carrier',) if node['type'] == 'BOUNDARY' else ('base', 'fiber')
    return [{'path': [role] + s['path'], 'class': s['class']}
            for role in roles for s in selectors(node[role])]


def _transport(node):
    if node['type'] == 'FACTORS':
        return f.apply('dual_all', [node])
    roles = ('carrier',) if node['type'] == 'BOUNDARY' else ('base', 'fiber')
    return dict(node, **{r: _transport(node[r]) for r in roles})


def _component(node, path, cls):
    if not path:
        return f.apply('dual_component', [node], {'class': cls})
    role = path[0]
    return dict(node, **{role: _component(node[role], path[1:], cls)})


def apply(operator, inputs, parameters=None):
    inputs = [normalize(n) for n in inputs]
    parameters = {} if parameters is None else parameters
    if not isinstance(parameters, dict):
        raise ValueError('parameters must be an object')
    arities = {'close': 1, 'compose': 2, 'fiber': 2, 'boundary': 1,
               'dual_all': 1, 'dual_base': 1, 'dual_fiber': 1, 'dual_component': 1}
    if operator not in arities or len(inputs) != arities[operator]:
        raise ValueError('unknown operator or wrong arity')
    if operator != 'dual_component' and parameters:
        raise ValueError('unexpected parameters')
    if operator in ('close', 'compose'):
        return f.apply(operator, inputs, parameters)
    if operator == 'fiber':
        return normalize({'type': 'FIBER', 'base': inputs[0], 'fiber': inputs[1]})
    node = inputs[0]
    if operator == 'boundary':
        return normalize({'type': 'BOUNDARY', 'carrier': node, 'rank': max(_dimension(node)-1, 0)})
    if node['type'] == 'RECURRENCE':
        raise ValueError('dual action requires generated structure')
    if operator == 'dual_all':
        return normalize(_transport(node))
    if operator in ('dual_base', 'dual_fiber'):
        if node['type'] != 'FIBER':
            raise ValueError('role action requires fiber structure')
        role = 'base' if operator == 'dual_base' else 'fiber'
        return normalize(dict(node, **{role: _transport(node[role])}))
    if set(parameters) != {'path', 'class'} or canonical(parameters) not in {canonical(s) for s in selectors(node)}:
        raise ValueError('component selector must specify a present intrinsic path and class')
    return normalize(_component(node, parameters['path'], parameters['class']))


def legacy_projection(node):
    node = normalize(node)
    if node['type'] in ('RECURRENCE', 'FACTORS'):
        return f.legacy_projection(node)
    if node['type'] == 'BOUNDARY':
        carrier = legacy_projection(node['carrier'])
        return None if carrier is None else dict(carrier, kind='BOUNDARY', dim=node['rank'], sq=None, anti=None)
    base, fiber = legacy_projection(node['base']), legacy_projection(node['fiber'])
    if base is None or fiber is None or any(base[k] != fiber[k] for k in ('order', 'sym', 'bc', 'dual')):
        return None
    return dict(base, kind='BUNDLE', dim=_dimension(node['base']), sq=None, anti=None,
                mult=max(base['mult'], fiber['mult']), sym=fiber['sym'], occ=fiber['occ'])


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
    for e in sorted(graph['events'], key=lambda e: e['level']):
        if e['version'] != expected_version or e['id'] != digest(event_identity(e)):
            raise ValueError('invalid event version or hash')
        if e['id'] in seen:
            raise ValueError('duplicate event')
        seen.add(e['id'])
        if not f._integer(e['level'], 1) or any(i not in reached or reached[i] >= e['level'] for i in e['inputs']):
            raise ValueError('inputs lack earlier seed-rooted derivations')
        output = apply(e['operator'], [nodes[i] for i in e['inputs']], e['parameters'])
        if e['output'] not in nodes or output != nodes[e['output']]:
            raise ValueError('replay output mismatch')
        reached.setdefault(e['output'], e['level'])
    if reached.keys() != nodes.keys():
        raise ValueError('unreachable nodes')
    return {'clean': True, 'replayed_events': len(seen), 'seed_rooted_nodes': len(reached)}
