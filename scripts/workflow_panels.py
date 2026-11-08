"""Fold a ComfyUI UI workflow into one controls panel, offline, and prove the fold changed nothing.

`fold_into_panel` keeps the chosen input/output nodes and notes on the canvas, moves every other node
into one new subgraph, and turns the listed controls into labelled fields on it. Each field drives a
pass-through primitive inside the panel, the same structure ComfyUI's frontend writes when it converts
a selection to a subgraph. `flatten` resolves every subgraph, primitive and panel field down to plain
node inputs, so a workflow can be compared before and after folding.
"""
import copy, re, uuid

PRIMITIVES = {'PrimitiveInt': 'INT', 'PrimitiveFloat': 'FLOAT', 'PrimitiveBoolean': 'BOOLEAN',
              'PrimitiveString': 'STRING', 'PrimitiveStringMultiline': 'STRING'}


def _link(l):
    """(id, origin_id, origin_slot, target_id, target_slot, type) for either link format."""
    if isinstance(l, dict):
        return l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l.get('type')
    return tuple(l[:6])


def _definitions(data):
    return {s['id']: s for s in data.get('definitions', {}).get('subgraphs', [])}


def _widget_value(node, input_name):
    """Value of an unlinked widget input on a subgraph instance (widgets_values follow its widget inputs)."""
    if input_name in node.get('widgets_values_named',{}):return node['widgets_values_named'][input_name]
    widgets = [i['name'] for i in node.get('inputs', []) if i.get('widget')]
    values = node.get('widgets_values') or []
    if input_name in widgets and len(values) == len(widgets):
        return values[widgets.index(input_name)]
    return None


def flatten(data):
    """{node path: (type, widgets_values, {input: resolved source})} with subgraphs and primitives resolved away."""
    defs = _definitions(data)
    out = {}

    def walk(graph, path, parent):
        nodes = {n['id']: n for n in graph.get('nodes', [])}
        links = {_link(l)[0]: _link(l) for l in graph.get('links', [])}

        def resolve(link_id):
            _, origin, slot, _, _, _ = links[link_id]
            if origin == -10:  # subgraph input: follow the instance's input in the parent graph
                inst, parent_resolve = parent
                name = graph['inputs'][slot]['name']
                inp = next((i for i in inst.get('inputs',[]) if i['name'] == name),None)
                if inp and inp.get('link') is not None:return parent_resolve(inp['link'])
                value=_widget_value(inst,name)
                if value is None:
                    _,_,_,target,target_slot,_=links[link_id]
                    value=_widget_value(nodes[target],nodes[target]['inputs'][target_slot]['name'])
                return ('value',value)
            node = nodes[origin]
            if node['type']=='Reroute':return resolve(node['inputs'][0]['link'])
            if node.get('mode')==4:
                candidates=[i for i in node.get('inputs',[]) if i.get('link') is not None and (i.get('type') in (links[link_id][5],'*') or links[link_id][5] in str(i.get('type','')).split(','))]
                if candidates:return resolve(candidates[0]['link'])
            if node['type'] in PRIMITIVES:
                value_input = next((i for i in node.get('inputs', []) if i['name'] == 'value'), None)
                if value_input and value_input.get('link') is not None:
                    return resolve(value_input['link'])
                return ('value', (node.get('widgets_values') or [None])[0])
            if node['type'] in defs:  # an inner panel's output: follow it to the node that feeds it
                sub = defs[node['type']]
                inner = next(_link(l) for l in sub['links'] if _link(l)[3] == -20 and _link(l)[4] == slot)
                return walk_resolve(sub, path + (origin,), (node, resolve), inner[0])
            return ('node', path + (origin,), slot)

        for node in graph.get('nodes', []):
            if node.get('mode') in (2,4):continue
            if node['type'] in defs:
                walk(defs[node['type']], path + (node['id'],), (node, resolve))
            elif node['type'] not in PRIMITIVES and node['type'] not in ('MarkdownNote', 'Note', 'Reroute'):
                named=node.get('widgets_values_named')
                inputs={k:('value',v) for k,v in (named or {}).items()}
                inputs.update({i['name']: resolve(i['link']) for i in node.get('inputs', []) if i.get('link') is not None})
                out[path + (node['id'],)] = (node['type'], None if named else node.get('widgets_values'), inputs)
        return resolve

    cache = {}

    def walk_resolve(sub, path, parent, link_id):
        key = (sub['id'], path)
        if key not in cache:
            cache[key] = walk(sub, path, parent)
        return cache[key](link_id)

    walk(data, (), None)
    return out


def _strip(flat, prefix):
    """Drop the new panel's id from paths so a folded workflow compares with its original."""
    def fix(path):
        return path[1:] if path[:1] == (prefix,) else path
    result = {}
    for path, (typ, widgets, inputs) in flat.items():
        result[fix(path)] = (typ, widgets, {k: (v[0], fix(v[1]), v[2]) if v[0] == 'node' else v for k, v in inputs.items()})
    return result


def _slug(text, taken):
    name = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')[:40] or 'field'
    base, n = name, 1
    while name in taken:
        n += 1; name = f'{base}_{n}'
    taken.add(name)
    return name


def fold_into_panel(data, title, keep, fields, drop_notes=(), note_titles=None):
    """Fold `data` in place. `keep`: node ids that stay on the canvas (inputs and outputs).

    `fields` are panel controls in display order, either {'label', 'source': root primitive id} or
    {'label', 'kind': primitive class, 'targets': [(node id, input name), ...]} for a new control that
    drives widget inputs currently set on inner nodes.
    """
    nodes = {n['id']: n for n in data['nodes']}
    # Deliberate new defaults are applied first, so the equivalence check below covers only the fold.
    for field in fields:
        if 'value' in field:
            for node_id, input_name in field['targets']:
                widgets = [i['name'] for i in nodes[node_id]['inputs'] if i.get('widget')]
                nodes[node_id]['widgets_values'][widgets.index(input_name)] = field['value']
    before = flatten(data)
    defs = _definitions(data)
    for node_id in drop_notes:
        nodes.pop(node_id, None)
    for node_id, text in (note_titles or {}).items():
        nodes[node_id]['title'] = text
    notes = [n for n in nodes.values() if n['type'] in ('MarkdownNote', 'Note')]
    sources = {f['source'] for f in fields if 'source' in f}
    keep = set(keep)
    inner_ids = [i for i, n in nodes.items() if i not in keep and i not in sources and n['type'] not in ('MarkdownNote', 'Note')]
    dict_links = bool(data['links']) and isinstance(data['links'][0], dict)
    root_links = [_link(l) for l in data['links']]

    state = data.get('state') or {}
    next_node = max([n['id'] for g in [data] + list(defs.values()) for n in g.get('nodes', [])] + [data.get('last_node_id') or 0, state.get('lastNodeId', 0)]) + 1
    all_links = [_link(l)[0] for g in [data] + list(defs.values()) for l in g.get('links', [])]
    next_link = max(all_links + [data.get('last_link_id') or 0, state.get('lastLinkId', 0)]) + 1

    def new_link():
        nonlocal next_link
        next_link += 1
        return next_link - 1

    sub_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'sulphur/{data.get("id")}/{title}'))
    sub_links, keep_root, taken = [], [], set()
    io_inputs, io_outputs = {}, {}  # (origin, slot) -> spec ; (origin, slot) -> spec
    for lid, o, os_, t, ts, ty in root_links:
        if o in sources or t in sources:
            continue
        o_in, t_in = o in inner_ids, t in inner_ids
        if o_in and t_in:
            sub_links.append({'id': lid, 'origin_id': o, 'origin_slot': os_, 'target_id': t, 'target_slot': ts, 'type': ty})
        elif not o_in and t_in:
            spec = io_inputs.setdefault((o, os_), {'type': ty, 'label': nodes[o].get('title') or nodes[o]['type'],
                                                  'name': nodes[t]['inputs'][ts]['name'], 'inner': []})
            spec['inner'].append((lid, t, ts))
        elif o_in and not t_in:
            spec = io_outputs.setdefault((o, os_), {'type': ty, 'name': nodes[o]['outputs'][os_].get('name') or ty, 'outer': []})
            spec['outer'].append((t, ts))
            spec['inner_link'] = spec.get('inner_link') or lid
        else:
            keep_root.append((lid, o, os_, t, ts, ty))

    relays, sub_inputs, values = [], [], []
    for field in fields:
        if 'source' in field:
            prim = nodes[field['source']]
            kind, value = prim['type'], (prim.get('widgets_values') or [None])[0]
            feeds = [(lid, t, ts) for lid, o, _, t, ts, _ in root_links if o == field['source']]
            assert all(t in inner_ids for _, t, _ in feeds), f'{field["label"]}: control feeds a node kept on the canvas'
        else:
            kind = field['kind']
            first_node, first_input = field['targets'][0]
            value = _widget_value(nodes[first_node], first_input)
            feeds = []
            for node_id, input_name in field['targets']:
                slot = next(k for k, i in enumerate(nodes[node_id]['inputs']) if i['name'] == input_name)
                assert nodes[node_id]['inputs'][slot].get('link') is None, f'{field["label"]}: {node_id}.{input_name} is already wired'
                lid = new_link()
                nodes[node_id]['inputs'][slot]['link'] = lid
                feeds.append((lid, node_id, slot))
        typ = PRIMITIVES[kind]
        relay_id = next_node; next_node += 1
        in_link = new_link()
        relays.append({'id': relay_id, 'type': kind, 'pos': [0, 120 * len(relays)], 'size': [300, 60], 'flags': {}, 'order': 0, 'mode': 0,
                       'inputs': [{'localized_name': 'value', 'name': 'value', 'type': typ, 'widget': {'name': 'value'}, 'link': in_link}],
                       'outputs': [{'localized_name': typ, 'name': typ, 'type': typ, 'links': [lid for lid, _, _ in feeds]}],
                       'title': field['label'], 'properties': {'Node name for S&R': kind}, 'widgets_values': [value],
                       'widgets_values_named': {'value': value}})
        for lid, t, ts in feeds:
            sub_links.append({'id': lid, 'origin_id': relay_id, 'origin_slot': 0, 'target_id': t, 'target_slot': ts, 'type': typ})
        name = _slug(field['label'], taken)
        sub_inputs.append({'name': name, 'type': typ, 'label': field['label'], 'links': [in_link], 'field': True,
                           'relay': relay_id})
        values.append(value)
    for (o, os_), spec in io_inputs.items():
        spec['name'] = _slug(spec['name'], taken)
        sub_inputs.append({'name': spec['name'], 'type': spec['type'], 'label': spec['label'], 'links': [l for l, _, _ in spec['inner']],
                           'source': (o, os_), 'inner': spec['inner']})

    panel_id = next_node
    panel_inputs, panel_links, def_inputs = [], [], []
    for index, spec in enumerate(sub_inputs):
        if spec.get('field'):
            sub_links.append({'id': spec['links'][0], 'origin_id': -10, 'origin_slot': index, 'target_id': spec['relay'], 'target_slot': 0, 'type': spec['type']})
            panel_inputs.append({'label': spec['label'], 'localized_name': spec['name'], 'name': spec['name'], 'type': spec['type'],
                                 'widget': {'name': spec['name']}, 'link': None})
        else:
            for lid, t, ts in spec['inner']:
                sub_links.append({'id': lid, 'origin_id': -10, 'origin_slot': index, 'target_id': t, 'target_slot': ts, 'type': spec['type']})
            root_link = new_link()
            o, os_ = spec['source']
            panel_links.append((root_link, o, os_, panel_id, index, spec['type']))
            panel_inputs.append({'label': spec['label'], 'localized_name': spec['name'], 'name': spec['name'], 'type': spec['type'], 'link': root_link})
        def_inputs.append({'id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'{sub_id}/in/{spec["name"]}')), 'name': spec['name'], 'type': spec['type'],
                           'linkIds': spec['links'], 'localized_name': spec['name'], 'label': spec['label'], 'pos': [0, 20 * index]})
    panel_outputs, def_outputs = [], []
    for index, ((o, os_), spec) in enumerate(io_outputs.items()):
        sub_links.append({'id': spec['inner_link'], 'origin_id': o, 'origin_slot': os_, 'target_id': -20, 'target_slot': index, 'type': spec['type']})
        outer = []
        for t, ts in spec['outer']:
            lid = new_link(); outer.append(lid)
            panel_links.append((lid, panel_id, index, t, ts, spec['type']))
        panel_outputs.append({'label': spec['name'], 'localized_name': spec['name'], 'name': spec['name'], 'type': spec['type'], 'links': outer})
        def_outputs.append({'id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'{sub_id}/out/{spec["name"]}/{index}')), 'name': spec['name'], 'type': spec['type'],
                            'linkIds': [spec['inner_link']], 'localized_name': spec['name'], 'label': spec['name'], 'pos': [0, 20 * index]})

    inner_nodes = [nodes[i] for i in inner_ids] + relays
    xs = [n['pos'][0] for n in inner_nodes if 'pos' in n] or [0]
    ys = [n['pos'][1] for n in inner_nodes if 'pos' in n] or [0]
    definition = {'id': sub_id, 'version': 1, 'state': {'lastGroupId': state.get('lastGroupId', 0), 'lastNodeId': next_node, 'lastLinkId': next_link,
                  'lastRerouteId': state.get('lastRerouteId', 0)}, 'revision': 0, 'config': {}, 'name': title,
                  'inputNode': {'id': -10, 'bounding': [min(xs) - 400, min(ys), 160, 40 + 20 * len(def_inputs)]},
                  'outputNode': {'id': -20, 'bounding': [max(xs) + 600, min(ys), 140, 40 + 20 * len(def_outputs)]},
                  'inputs': def_inputs, 'outputs': def_outputs, 'widgets': [], 'nodes': inner_nodes, 'groups': [], 'links': sub_links, 'extra': {}}
    for k, relay in enumerate(relays):
        relay['pos'] = [min(xs) - 380, min(ys) + 200 + 100 * k]

    panel = {'id': panel_id, 'type': sub_id, 'pos': [420, 0], 'size': [560, 120 + 30 * len(panel_inputs)], 'flags': {}, 'order': 0, 'mode': 0,
             'inputs': panel_inputs, 'outputs': panel_outputs, 'title': title, 'properties': {'cnr_id': 'comfy-core', 'ver': '0.39.0'},
             'widgets_values': values,
             'widgets_values_named': {i['name']: v for i, v in zip([i for i in panel_inputs if i.get('widget')], values)}}
    kept = [nodes[i] for i in nodes if i in keep]
    is_output = lambda n: n['type'].startswith(('Save', 'Preview'))
    for k, node in enumerate(n for n in kept if is_output(n)):
        node['pos'] = [1060, 260 * k]
    for k, node in enumerate(n for n in kept if not is_output(n)):
        node['pos'] = [0, 340 * k]
    y = 0
    for note in notes:
        note['pos'] = [-560, y]; y += min(note.get('size', [0, 300])[1], 420) + 60
    for node in kept:  # their links now run to and from the panel
        for inp in node.get('inputs', []):
            match = [l for l in panel_links if l[3] == node['id'] and l[4] == node['inputs'].index(inp)]
            if match: inp['link'] = match[0][0]
        for slot, out in enumerate(node.get('outputs', [])):
            out['links'] = [l[0] for l in keep_root + panel_links if l[1] == node['id'] and l[2] == slot]

    links = keep_root + panel_links
    data['links'] = [{'id': l[0], 'origin_id': l[1], 'origin_slot': l[2], 'target_id': l[3], 'target_slot': l[4], 'type': l[5]} if dict_links else list(l)
                     for l in links]
    data['nodes'] = kept + notes + [panel]
    # Reroute points and floating links are drawing aids; drop any whose connection moved into the panel.
    remaining = {l[0] for l in links}
    if 'reroutes' in data:
        data['reroutes'] = [r for r in data['reroutes'] if set(r.get('linkIds', [])) & remaining]
    if 'floatingLinks' in data:
        canvas = {n['id'] for n in data['nodes']}
        data['floatingLinks'] = [l for l in data['floatingLinks'] if l.get('origin_id') in canvas or l.get('target_id') in canvas]
    data.setdefault('definitions', {}).setdefault('subgraphs', []).append(definition)
    if 'state' in data: data['state'].update(lastNodeId=next_node, lastLinkId=next_link)
    if 'last_node_id' in data: data['last_node_id'] = next_node
    if 'last_link_id' in data: data['last_link_id'] = next_link

    after = _strip(flatten(data), panel_id)
    if after != before:
        diffs = sorted(set(before) ^ set(after))[:5] or [p for p in before if before[p] != after.get(p)][:5]
        raise AssertionError(f'{title}: folding changed the workflow at {diffs}')
    return data
