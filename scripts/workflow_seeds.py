"""Resolve seed drivers through subgraph boundaries; preserve non-seed integer controls."""
import re


def apply_seed_defaults(data):
    definitions = {g['id']: g for g in data.get('definitions', {}).get('subgraphs', [])}
    drivers, unresolved = set(), []

    def seed_input(inp):
        return bool(re.search(r'(^|_)seed(?:_\d+)?$', inp['name']) or re.search(r'\bseed\b', inp.get('label', ''), re.I))

    def resolve(graph, node, inp, parents, seen):
        key = (id(graph), node['id'], inp['name'])
        if key in seen:
            return None
        seen = seen | {key}
        link_id = inp.get('link')
        if link_id is None:
            return node, inp['name']
        links = {l['id'] if isinstance(l, dict) else l[0]: l for l in graph.get('links', [])}
        link = links[link_id]
        origin, slot = (link['origin_id'], link['origin_slot']) if isinstance(link, dict) else link[1:3]
        if origin == -10:
            if not parents:
                return None
            parent, instance = parents[-1]
            name = graph['inputs'][slot]['name']
            outer = next((i for i in instance.get('inputs', []) if i['name'] == name), None)
            # Legacy exports omit promoted inputs from the instance while the definition
            # still supplies their widgets. Track that actual outer control by its name.
            return resolve(parent, instance, outer or {'name': name}, parents[:-1], seen)
        source = next(n for n in graph['nodes'] if n['id'] == origin)
        if source['type'] in ('PrimitiveInt', 'PrimitiveNode', 'Reroute'):
            value = next((i for i in source.get('inputs', []) if i['name'] == 'value'), {'name': 'value'})
            return resolve(graph, source, value, parents, seen)
        if source['type'] in definitions:
            sub = definitions[source['type']]
            output = sub['outputs'][slot]
            inner_link = (output.get('linkIds') or output.get('links') or [None])[0]
            boundary = next((l for l in sub['links'] if (l['id'] if isinstance(l, dict) else l[0]) == inner_link), None)
            if boundary:
                source_id = boundary['origin_id'] if isinstance(boundary, dict) else boundary[1]
                inner = next(n for n in sub['nodes'] if n['id'] == source_id)
                return resolve(sub, inner, {'name': 'value'}, parents + [(graph, source)], seen)
        return None

    def record(node, field):
        drivers.add((id(node), field))
        if node['type'] in ('PrimitiveInt', 'PrimitiveNode'):
            node.setdefault('properties', {})['acdevSeedDriver'] = True
        values = node.get('widgets_values') or []
        # Only seed drivers get this change; dimensions and durations stay fixed.
        for index, value in enumerate(values):
            if value in ('fixed', 'increment', 'decrement'):
                values[index] = 'randomize'
        node.setdefault('properties', {}).setdefault('acdevSeedModes', {}).setdefault(field, 'randomize')

    def walk(graph, parents):
        for node in graph.get('nodes', []):
            inputs = [i for i in node.get('inputs', []) if seed_input(i)]
            if not inputs:
                field = {'KSampler': 'seed', 'KSamplerAdvanced': 'noise_seed', 'RandomNoise': 'noise_seed',
                         'AcdevFluxStudio': 'seed', 'AcdevIdeogramStudio': 'seed'}.get(node['type'])
                if field:
                    inputs = [{'name': field}]
            for inp in inputs:
                driver = resolve(graph, node, inp, parents, set())
                if driver:
                    record(*driver)
                else:
                    unresolved.append((node['id'], inp['name']))
            if node['type'] in definitions:
                walk(definitions[node['type']], parents + [(graph, node)])
    walk(data, [])
    return len(drivers), unresolved
