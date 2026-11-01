"""Explicit human-reviewed minimal scene structure; design truths remain noncanon."""
from __future__ import annotations

import json
from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.models.authoring import AuthoringSession
from storygraph.models.writer_visibility import WriterVisibilityPolicy
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.longform_planning import _clone
from storygraph.stores.memory_graph import InMemoryGraphStore


def _id(session, kind, local):
    return 'as_' + kind + '_' + content_hash(canonical_json([session.project_id, session.id, local]))[:32]


def _card(session, card_id):
    card = next((c for c in session.workspace.scene_cards if c.id == card_id), None)
    if card is None:
        raise ContractError('authoring_card_not_found')
    if card.status != 'approved':
        raise ContractError('authoring_card_not_approved')
    return card


def _project(graph, project_id):
    project = graph.get_node(project_id)
    if project.type != 'Project':
        raise ContractError('authoring_project_not_found')


def _scoped(graph, project_id):
    return sorted([n.model_dump(mode='json') for n in graph.nodes.values()
                   if n.status == 'CANON' and (n.id == project_id or n.properties.get('project_id') == project_id)], key=lambda n: n['id'])


def preview_structure(graph, session, card_id):
    """Return the complete reviewable write set without mutating graph or design."""
    _project(graph, session.project_id)
    card = _card(session, card_id)
    if card.scene_id:
        return _preview_update(graph, session, card)
    gaps = [field for field in ('chapter_title', 'location', 'timeline_position', 'goal', 'conflict', 'emotional_turn', 'intended_outcome')
            if not getattr(card, field).strip()]
    if not card.pov_character_id:
        gaps.append('pov_character_id')
    mapping, nodes, reuse = {}, [], []
    names = set()
    def node(kind, identity, props):
        nodes.append({'id': identity, 'type': kind, 'properties': {'project_id': session.project_id, **props}})
    for actor in card.writer_policy.characters:
        if actor.public_name.strip() in names:
            raise ContractError('authoring_structure_name_collision')
        names.add(actor.public_name.strip())
        existing = graph.nodes.get(actor.character_id)
        identity = actor.character_id if existing else _id(session, 'character', actor.character_id)
        target = existing or graph.nodes.get(identity)
        if target:
            if target.status != 'CANON' or target.type != 'Character' or target.properties.get('project_id') != session.project_id:
                raise ContractError('authoring_structure_character_foreign')
            if identity != actor.character_id and not target.source_ref.startswith('authoring_structure:' + session.id + ':'):
                raise ContractError('authoring_structure_character_foreign')
            reuse.append({'id':target.id, 'type':'Character', 'name':target.properties.get('name'), 'public_name':actor.public_name})
        else:
            if any(n.type == 'Character' and n.properties.get('name', '').strip() == actor.public_name.strip() for n in graph.nodes.values()
                   if n.status == 'CANON' and n.properties.get('project_id') == session.project_id):
                raise ContractError('authoring_structure_name_collision')
            node('Character', identity, {'name': actor.public_name})
        mapping[actor.character_id] = identity
    if card.pov_character_id and card.pov_character_id not in mapping:
        gaps.append('pov_public_name')
    scene_id, chapter_id = _id(session, 'scene', card.id), _id(session, 'chapter', card.id)
    location_id = _id(session, 'location', card.id)
    if card.location.strip():
        existing_location = graph.nodes.get(card.location)
        if existing_location:
            if existing_location.status != 'CANON' or existing_location.type != 'Location' or existing_location.properties.get('project_id') != session.project_id:
                raise ContractError('authoring_structure_location_foreign')
            location_id = existing_location.id
            reuse.append({'id':location_id, 'type':'Location', 'name':existing_location.properties.get('name')})
        elif any(n.type == 'Location' and n.properties.get('name', '').strip() == card.location.strip() for n in graph.nodes.values()
               if n.status == 'CANON' and n.properties.get('project_id') == session.project_id):
            raise ContractError('authoring_structure_name_collision')
        else:
            node('Location', location_id, {'name': card.location})
    node('Chapter', chapter_id, {'title': card.chapter_title, 'target_length': card.target_length})
    props = {'title': card.title, 'chapter_id': chapter_id, 'scene_index': 1, 'previous_scene_id': None,
             'require_semantic_review': True,
             'pov_character_id': mapping.get(card.pov_character_id), 'location_id': location_id,
             'required_characters': list(mapping.values()), 'timeline_position': card.timeline_position,
             'goal': card.goal, 'conflict': card.conflict, 'emotional_turn': card.emotional_turn,
             'outcome': card.intended_outcome, 'target_length': card.target_length}
    # A projection is a prose permission subset, never a replacement for the
    # complete canonical project style inherited by this new Scene.
    if card.writer_policy.writer_style_origin == 'author_literal':
        literal_style = {k:v for k,v in card.writer_policy.writer_style.model_dump(mode='json', exclude_none=True).items() if v}
        if literal_style:
            props['style_constraints'] = literal_style
    if card.author_summary.strip():
        props['summary'] = card.author_summary
    elif card.writer_policy.surface_plan.kind == 'literal':
        props['summary'] = card.writer_policy.surface_plan.text
    node('Scene', scene_id, props)
    relationships = []
    for kind, source, target in [('HAS_CHAPTER', session.project_id, chapter_id), ('HAS_SCENE', chapter_id, scene_id)]:
        relationships.append({'id': _id(session, 'relation', kind + card.id), 'type': kind, 'source_id': source, 'target_id': target,
                              'properties': {'project_id': session.project_id}})
    return {'operation': 'create', 'current_scene': None, 'changes': [], 'source_sha256': content_hash(canonical_json({'card': card.model_dump(mode='json'), 'graph': _scoped(graph, session.project_id),
            'relationships': sorted([r.model_dump(mode='json') for r in graph.relationships.values() if r.properties.get('project_id') == session.project_id], key=lambda r: r['id'])})),
            'card_version': card.version, 'scene_id': scene_id, 'chapter_id': chapter_id, 'nodes': nodes,
            'relationships': relationships, 'character_mapping': mapping, 'gaps': gaps, 'reuse':reuse}


def _preview_update(graph, session, card):
    scene = graph.get_node(card.scene_id)
    if scene.type != 'Scene' or scene.properties.get('project_id') != session.project_id:
        raise ContractError('authoring_structure_scene_mismatch')
    mapping, gaps, reuse = {}, [], []
    for actor in card.writer_policy.characters:
        ref = actor.character_id if actor.character_id in graph.nodes else _id(session, 'character', actor.character_id)
        node = graph.nodes.get(ref)
        if (node is None or node.status != 'CANON' or node.type != 'Character'
            or node.properties.get('project_id') != session.project_id
            or (ref != actor.character_id and not node.source_ref.startswith('authoring_structure:' + session.id + ':'))):
            gaps.append('character_mapping:' + actor.character_id)
        else:
            mapping[actor.character_id] = ref
            reuse.append({'id':node.id,'type':'Character','name':node.properties.get('name'),'public_name':actor.public_name})
    props = {}
    if card.author_summary.strip():
        props['summary'] = card.author_summary
    for field, target in [('title','title'), ('timeline_position','timeline_position'), ('goal','goal'), ('conflict','conflict'),
                          ('intended_outcome','outcome'), ('emotional_turn','emotional_turn')]:
        value = getattr(card, field)
        if value.strip():
            props[target] = value
    props.update(target_length=card.target_length,
                 required_characters=list(mapping.values()), require_semantic_review=True)
    if card.pov_character_id:
        if card.pov_character_id not in mapping:
            gaps.append('pov_public_name')
        else:
            props['pov_character_id'] = mapping[card.pov_character_id]
    location = graph.nodes.get(card.location)
    current_location = graph.nodes.get(scene.properties.get('location_id'))
    if card.location.strip():
        if location and location.status == 'CANON' and location.type == 'Location' and location.properties.get('project_id') == session.project_id:
            props['location_id'] = location.id
        elif current_location and current_location.properties.get('name') == card.location:
            props['location_id'] = current_location.id
        else:
            gaps.append('location_mapping')
        if 'location_id' in props:
            reused_location = graph.get_node(props['location_id'])
            reuse.append({'id':reused_location.id,'type':'Location','name':reused_location.properties.get('name')})
    changes = [{'field': key, 'before': scene.properties.get(key), 'after': value} for key, value in props.items() if scene.properties.get(key) != value]
    source = {'card': card.model_dump(mode='json'), 'graph': _scoped(graph, session.project_id),
              'relationships': sorted([r.model_dump(mode='json') for r in graph.relationships.values() if r.properties.get('project_id') == session.project_id], key=lambda r: r['id'])}
    return {'operation':'update', 'current_scene':scene.model_dump(mode='json'), 'changes':changes,
            'source_sha256':content_hash(canonical_json(source)), 'card_version':card.version, 'scene_id':scene.id,
            'chapter_id':scene.properties.get('chapter_id'), 'nodes':[{'id':scene.id,'type':'Scene','properties':props}],
            'relationships':[], 'character_mapping':mapping, 'gaps':gaps, 'reuse':reuse}


def _table(store):
    store._connection.execute('CREATE TABLE IF NOT EXISTS authoring_structure_receipts (project_id TEXT, session_id TEXT, card_id TEXT, payload TEXT NOT NULL, PRIMARY KEY(project_id,session_id,card_id))')
    store._connection.commit()


def apply_structure(graph, authoring_store, project_id, session_id, card_id, expected_version, card_version,
                    source_sha256, reviewer, rationale, persist_snapshot):
    """Stage/persist graph, then CAS design receipt. Exact durable events permit recovery."""
    if not isinstance(graph, InMemoryGraphStore):
        raise ContractError('authoring_structure_local_graph_required')
    if not reviewer.strip() or not rationale.strip():
        raise ContractError('authoring_structure_review_required')
    store = authoring_store
    with graph.persistence_guard(), store._lock:
        _project(graph, project_id)
        _table(store)
        session = AuthoringSession.model_validate(store.get(project_id, session_id))
        current_card = _card(session, card_id)
        if current_card.scene_id:
            # Historical create retries retain their original receipt semantics.
            created = store._connection.execute('SELECT payload FROM authoring_structure_receipts WHERE project_id=? AND session_id=? AND card_id=?', (project_id, session_id, card_id)).fetchone()
            original = json.loads(created[0]) if created else None
            if original is None or original['source_sha256'] != source_sha256:
                return _apply_update(graph, store, session, current_card, expected_version, card_version,
                                     source_sha256, reviewer, rationale, persist_snapshot)
        row = store._connection.execute('SELECT payload FROM authoring_structure_receipts WHERE project_id=? AND session_id=? AND card_id=?', (project_id, session_id, card_id)).fetchone()
        receipt = json.loads(row[0]) if row else None
        if receipt and receipt['source_sha256'] != source_sha256:
            raise ContractError('authoring_structure_source_stale')
        if receipt and receipt['card_version'] != card_version:
            raise ContractError('authoring_structure_card_stale')
        if receipt and receipt.get('completed'):
            return {'session': session, 'scene_id': receipt['scene_id'], 'chapter_id': receipt['chapter_id']}
        card = _card(session, card_id)
        # Session CAS can commit before the final SQL receipt marker. Its exact
        # recorded binding is sufficient for idempotent completion, never a rebind.
        if receipt and card.scene_id == receipt['scene_id']:
            if card.version < receipt['card_version'] + 1:
                raise ContractError('authoring_structure_invalid_receipt')
            receipt['completed'] = True
            store._connection.execute('UPDATE authoring_structure_receipts SET payload=? WHERE project_id=? AND session_id=? AND card_id=?', (json.dumps(receipt, ensure_ascii=False), project_id, session_id, card_id))
            store._connection.commit()
            return {'session': session, 'scene_id': receipt['scene_id'], 'chapter_id': receipt['chapter_id']}
        if session.version != expected_version or card.version != card_version or session.turn_status == 'running':
            raise ContractError('authoring_stale_version')
        if receipt and receipt['card_sha256'] != content_hash(canonical_json(card.model_dump(mode='json'))):
            raise ContractError('authoring_structure_card_stale')
        if receipt is None:
            preview = preview_structure(graph, session, card_id)
            if preview['source_sha256'] != source_sha256:
                raise ContractError('authoring_structure_source_stale')
            if preview['gaps']:
                raise ContractError('authoring_structure_gaps:' + ','.join(preview['gaps']))
            receipt = {**preview, 'reviewer': reviewer, 'rationale': rationale, 'completed': False,
                       'card_sha256': content_hash(canonical_json(card.model_dump(mode='json')))}
            store._connection.execute('INSERT INTO authoring_structure_receipts VALUES (?,?,?,?)', (project_id, session_id, card_id, json.dumps(receipt, ensure_ascii=False)))
            store._connection.commit()
        source_ref = 'authoring_structure:' + session_id + ':' + card_id + ':' + source_sha256
        events = [e for e in graph.event_log.list() if e.source_ref == source_ref]
        specs = receipt['nodes'] + receipt['relationships']
        if events:
            expected = {s['id']: s for s in specs}
            if len(events) != len(expected) or {e.target for e in events} != set(expected):
                raise ContractError('authoring_structure_incomplete_receipt')
            for event in events:
                spec = expected[event.target]
                payload = event.payload
                if (event.operation != ('create_relation' if 'source_id' in spec else 'create_node') or not event.reviewer or not event.rationale
                    or payload.get('source_ref') != source_ref or any(payload.get(k) != v for k, v in spec.items())):
                    raise ContractError('authoring_structure_invalid_receipt')
                target = graph.relationships.get(event.target) if 'source_id' in spec else graph.nodes.get(event.target)
                if target is None or target.status != 'CANON' or target.properties.get('project_id') != project_id or target.type != spec['type']:
                    raise ContractError('authoring_structure_missing_target')
        else:
            # A pending SQL intent alone is never authority for a changed graph.
            current = preview_structure(graph, session, card_id)
            if current['source_sha256'] != source_sha256:
                raise ContractError('authoring_structure_source_stale')
            if any(s['id'] in graph.nodes or s['id'] in graph.relationships for s in specs):
                raise ContractError('authoring_structure_id_collision')
            staged = _clone(graph)
            provenance = {'source_ref': source_ref, 'reviewer': receipt['reviewer'], 'rationale': receipt['rationale']}
            for spec in receipt['nodes']:
                staged.seed_canon_node(node_id=spec['id'], node_type=spec['type'], properties=spec['properties'], **provenance)
            for spec in receipt['relationships']:
                staged.seed_canon_relation(relation_id=spec['id'], relation_type=spec['type'], source_id=spec['source_id'], target_id=spec['target_id'], properties=spec['properties'], **provenance)
            persist_snapshot(staged)
            graph.nodes, graph.relationships, graph.event_log = staged.nodes, staged.relationships, staged.event_log
        card.scene_id, card.version = receipt['scene_id'], card.version + 1
        session.version += 1
        session.updated_at = utc_now()
        session = AuthoringSession.model_validate(store.save(session, expected_version=expected_version))
        receipt['completed'] = True
        store._connection.execute('UPDATE authoring_structure_receipts SET payload=? WHERE project_id=? AND session_id=? AND card_id=?', (json.dumps(receipt, ensure_ascii=False), project_id, session_id, card_id))
        store._connection.commit()
        return {'session': session, 'scene_id': receipt['scene_id'], 'chapter_id': receipt['chapter_id']}


def _apply_update(graph, store, session, card, expected_version, card_version, source_sha256, reviewer, rationale, persist_snapshot):
    store._connection.execute('CREATE TABLE IF NOT EXISTS authoring_structure_updates (project_id TEXT, session_id TEXT, card_id TEXT, source_sha256 TEXT, payload TEXT NOT NULL, PRIMARY KEY(project_id,session_id,card_id,source_sha256))')
    store._connection.commit()
    key = (session.project_id, session.id, card.id, source_sha256)
    row = store._connection.execute('SELECT payload FROM authoring_structure_updates WHERE project_id=? AND session_id=? AND card_id=? AND source_sha256=?', key).fetchone()
    receipt = json.loads(row[0]) if row else None
    if receipt and receipt['card_version'] != card_version:
        raise ContractError('authoring_structure_card_stale')
    if receipt and receipt.get('completed'):
        return {'session':session, 'scene_id':receipt['scene_id'], 'chapter_id':receipt['chapter_id']}
    card_hash = content_hash(canonical_json(card.model_dump(mode='json')))
    # A graph-only update does not revise the design card or session, so its
    # original CAS remains exact across graph-persist/receipt crash recovery.
    if session.version != expected_version or card.version != card_version or session.turn_status == 'running':
        raise ContractError('authoring_stale_version')
    if receipt and receipt['card_sha256'] != card_hash:
        raise ContractError('authoring_structure_card_stale')
    if receipt is None:
        preview = _preview_update(graph, session, card)
        if preview['source_sha256'] != source_sha256:
            raise ContractError('authoring_structure_source_stale')
        if preview['gaps']:
            raise ContractError('authoring_structure_gaps:' + ','.join(preview['gaps']))
        receipt = {**preview, 'completed':False, 'card_sha256':card_hash, 'reviewer':reviewer, 'rationale':rationale}
        store._connection.execute('INSERT INTO authoring_structure_updates VALUES (?,?,?,?,?)', (*key,json.dumps(receipt,ensure_ascii=False)))
        store._connection.commit()
    source_ref = 'authoring_structure_update:' + session.id + ':' + card.id + ':' + source_sha256
    events = [e for e in graph.event_log.list() if e.source_ref == source_ref]
    props = receipt['nodes'][0]['properties']
    if events:
        if (len(events) != 1 or events[0].operation != 'update_node' or events[0].target != card.scene_id
            or events[0].payload != props or events[0].reviewer != receipt['reviewer'] or events[0].rationale != receipt['rationale']):
            raise ContractError('authoring_structure_invalid_receipt')
    else:
        if _preview_update(graph,session,card)['source_sha256'] != source_sha256:
            raise ContractError('authoring_structure_source_stale')
        staged = _clone(graph)
        staged.update_node(card.scene_id, props, source_ref=source_ref, reviewer=receipt['reviewer'], rationale=receipt['rationale'])
        persist_snapshot(staged)
        graph.nodes, graph.relationships, graph.event_log = staged.nodes, staged.relationships, staged.event_log
    receipt['completed'] = True
    store._connection.execute('UPDATE authoring_structure_updates SET payload=? WHERE project_id=? AND session_id=? AND card_id=? AND source_sha256=?', (json.dumps(receipt,ensure_ascii=False),*key))
    store._connection.commit()
    return {'session':session, 'scene_id':receipt['scene_id'], 'chapter_id':receipt['chapter_id']}


def resolve_card_policy(graph, store, session, card, target_scene_id):
    """Resolve only exact canonical IDs or reviewed local identity mappings."""
    scene = graph.get_node(target_scene_id)
    if scene.type != 'Scene' or scene.properties.get('project_id') != session.project_id or card.scene_id != target_scene_id:
        raise ContractError('authoring_structure_scene_mismatch')
    with store._lock:
        _table(store)
        row = store._connection.execute('SELECT payload FROM authoring_structure_receipts WHERE project_id=? AND session_id=? AND card_id=?', (session.project_id, session.id, card.id)).fetchone()
    receipt = json.loads(row[0]) if row else {}
    mapping = receipt.get('character_mapping', {}) if receipt.get('completed') else {}
    data = card.writer_policy.model_dump(mode='json')
    def resolve(identity):
        ref = mapping.get(identity, identity)
        node = graph.get_node(ref)
        if node.type != 'Character' or node.properties.get('project_id') != session.project_id:
            raise ContractError('authoring_structure_character_foreign')
        return ref
    for actor in data['characters']:
        actor['character_id'] = resolve(actor['character_id'])
    for claim in data['visible_claims']:
        if claim['character_id']:
            claim['character_id'] = resolve(claim['character_id'])
    return WriterVisibilityPolicy.model_validate(data)
