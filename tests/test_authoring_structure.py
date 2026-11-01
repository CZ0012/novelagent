"""Isolated minimal structure review, persistence and identity boundaries."""
import pytest
from storygraph.models.authoring import AuthoringSceneCard
from storygraph.services.authoring import AuthoringService
from storygraph.services.authoring_structure import preview_structure, apply_structure, resolve_card_policy
from storygraph.stores.memory_graph import InMemoryGraphStore
from storygraph.stores.authoring_store import SQLiteAuthoringStore
from storygraph.stores.proposal_store import SQLiteProposalStore
from storygraph.core.errors import ContractError


def setup():
    graph = InMemoryGraphStore()
    graph.seed_canon_node(node_id='project', node_type='Project', properties={'name': '故事', 'language': 'zh-CN'})
    store = SQLiteAuthoringStore(SQLiteProposalStore())
    service = AuthoringService(store=store)
    session = service.create(project_id='project', content_language='zh-CN', title='设计', idea='试写')
    session.workspace.scene_cards.append(AuthoringSceneCard(id='card', title='相遇', chapter_title='第一章', location='车站', timeline_position='清晨',
        goal='找到失物', conflict='列车即将发车', emotional_turn='希望转为担忧', intended_outcome='错过列车', status='approved', pov_character_id='local',
        writer_policy={'access_mode':'pov', 'surface_plan':{'kind':'literal','text':'她在车站寻找失物。'}, 'writer_style':{},
                       'characters':[{'character_id':'local','public_name':'小夏'}]}))
    session = service._save(session)
    return graph, store, session


def apply(graph, store, session, preview, persist=lambda g: None):
    return apply_structure(graph, store, 'project', session.id, 'card', session.version, preview['card_version'], preview['source_sha256'], '作者', '批准试写结构', persist)


def test_review_minimal_structure_and_idempotent_retry_preserve_author_edits():
    graph, store, session = setup()
    preview = preview_structure(graph, session, 'card')
    assert len(graph.nodes) == 1 and not preview['gaps']
    assert next(n for n in preview['nodes'] if n['type'] == 'Scene')['properties']['require_semantic_review'] is True
    result = apply(graph, store, session, preview)
    assert {n.type for n in graph.nodes.values()} == {'Project','Chapter','Scene','Character','Location'}
    assert {r.type for r in graph.relationships.values()} == {'HAS_CHAPTER','HAS_SCENE'}
    assert all(e.reviewer and e.rationale and e.source_ref for e in graph.event_log.list())
    saved = result['session']
    policy = resolve_card_policy(graph, store, saved, saved.workspace.scene_cards[0], result['scene_id'])
    assert policy.characters[0].character_id == preview['character_mapping']['local']
    assert saved.workspace.scene_cards[0].writer_policy.characters[0].character_id == 'local'
    graph.update_node(result['scene_id'], {'goal':'作者新目标'}, reviewer='作者', rationale='修改', source_ref='manual')
    count = len(graph.event_log.list())
    assert apply(graph, store, session, preview)['scene_id'] == result['scene_id']
    assert graph.get_node(result['scene_id']).properties['goal'] == '作者新目标'
    assert len(graph.event_log.list()) == count


def test_stale_source_gaps_foreign_identity_and_snapshot_failure_fail_closed():
    graph, store, session = setup()
    preview = preview_structure(graph, session, 'card')
    graph.update_node('project', {'name':'改名'}, reviewer='作者', rationale='修改', source_ref='manual')
    with pytest.raises(ContractError, match='source_stale'):
        apply(graph, store, session, preview)
    preview = preview_structure(graph, session, 'card')
    def fail(g):
        raise OSError('disk failure')
    with pytest.raises(OSError):
        apply(graph, store, session, preview, fail)
    assert len(graph.nodes) == 1
    result = apply(graph, store, session, preview)
    assert result['scene_id'] in graph.nodes


def test_graph_persisted_session_cas_failure_recovers_without_reapply(monkeypatch):
    graph, store, session = setup()
    preview = preview_structure(graph, session, 'card')
    original = store.save
    monkeypatch.setattr(store, 'save', lambda *a, **kw: (_ for _ in ()).throw(OSError('sql failure')))
    with pytest.raises(OSError):
        apply(graph, store, session, preview)
    count = len(graph.event_log.list())
    monkeypatch.setattr(store, 'save', original)
    result = apply(graph, store, session, preview)
    assert result['session'].workspace.scene_cards[0].scene_id == preview['scene_id']
    assert len(graph.event_log.list()) == count


def test_unknown_truth_remains_design_and_missing_outcome_requires_author():
    graph, store, session = setup()
    session.workspace.scene_cards[0].intended_outcome = ''
    session.version += 1
    session = type(session).model_validate(store.save(session, expected_version=session.version - 1))
    preview = preview_structure(graph, session, 'card')
    assert 'intended_outcome' in preview['gaps']
    with pytest.raises(ContractError, match='gaps'):
        apply(graph, store, session, preview)
    assert len(graph.nodes) == 1


def test_explicit_foreign_character_and_duplicate_name_cannot_bind():
    graph, store, session = setup()
    graph.seed_canon_node(node_id='local', node_type='Character', properties={'project_id':'other', 'name':'小夏'})
    with pytest.raises(ContractError, match='foreign'):
        preview_structure(graph, session, 'card')
    del graph.nodes['local']
    graph.seed_canon_node(node_id='another', node_type='Character', properties={'project_id':'project', 'name':'小夏'})
    with pytest.raises(ContractError, match='name_collision'):
        preview_structure(graph, session, 'card')


def test_actors_stable_across_cards_without_invented_world_order():
    graph, store, session = setup()
    result = apply(graph, store, session, preview_structure(graph, session, 'card'))
    saved = result['session']
    second = saved.workspace.scene_cards[0].model_copy(update={'id':'second', 'scene_id':None, 'location':'码头'})
    saved.workspace.scene_cards.append(second)
    saved.version += 1
    saved = type(saved).model_validate(store.save(saved, expected_version=saved.version - 1))
    preview = preview_structure(graph, saved, 'second')
    assert not any(n['type'] == 'Character' for n in preview['nodes'])
    assert preview['character_mapping']['local'] == graph.get_node(result['scene_id']).properties['pov_character_id']
    assert not any(r['type'] == 'NEXT_SCENE' for r in preview['relationships'])


def test_bound_card_plan_update_is_reviewed_and_preserves_summary_and_other_nodes():
    graph, store, session = setup()
    created = apply(graph, store, session, preview_structure(graph, session, 'card'))
    session = created['session']
    old_summary = graph.get_node(created['scene_id']).properties['summary']
    untouched = {ref: node.model_dump() for ref,node in graph.nodes.items() if ref != created['scene_id']}
    card = session.workspace.scene_cards[0]
    card.goal = '新的目标'
    card.conflict = '新的阻力'
    card.intended_outcome = '新的计划结果'
    card.timeline_position = '当天晚上'
    card.version += 1
    session.version += 1
    session = type(session).model_validate(store.save(session, expected_version=session.version - 1))
    preview = preview_structure(graph, session, 'card')
    assert preview['operation'] == 'update' and not preview['gaps']
    assert any(change['field'] == 'goal' for change in preview['changes'])
    assert 'summary' not in preview['nodes'][0]['properties']
    assert preview['relationships'] == []
    updated = apply(graph, store, session, preview)
    assert graph.get_node(created['scene_id']).properties['goal'] == card.goal
    assert graph.get_node(created['scene_id']).properties['summary'] == old_summary
    assert {ref:node.model_dump() for ref,node in graph.nodes.items() if ref != created['scene_id']} == untouched
    assert updated['session'].version == session.version
    graph.update_node(created['scene_id'], {'goal':'后来人工修改'}, reviewer='作者', rationale='修改', source_ref='manual')
    event_count = len(graph.event_log.list())
    apply(graph, store, session, preview)
    assert graph.get_node(created['scene_id']).properties['goal'] == '后来人工修改'
    assert len(graph.event_log.list()) == event_count


def test_bound_card_missing_new_identity_is_gap_and_stale_update_rejected():
    graph, store, session = setup()
    created = apply(graph, store, session, preview_structure(graph, session, 'card'))
    session = created['session']
    card = session.workspace.scene_cards[0]
    card.location = '未审核的新地点'
    session.version += 1
    session = type(session).model_validate(store.save(session, expected_version=session.version - 1))
    preview = preview_structure(graph, session, 'card')
    assert 'location_mapping' in preview['gaps']
    with pytest.raises(ContractError, match='gaps'):
        apply(graph, store, session, preview)
    card = session.workspace.scene_cards[0]
    card.location = '车站'
    session.version += 1
    session = type(session).model_validate(store.save(session, expected_version=session.version - 1))
    preview = preview_structure(graph, session, 'card')
    graph.update_node(created['scene_id'], {'goal':'外部修改'}, reviewer='作者', rationale='修改', source_ref='manual')
    with pytest.raises(ContractError, match='source_stale'):
        apply(graph, store, session, preview)


def test_bound_update_graph_persisted_receipt_failure_recovers_once():
    graph, store, session = setup()
    created = apply(graph, store, session, preview_structure(graph, session, 'card'))
    session = created['session']
    session.workspace.scene_cards[0].goal = '更新后的目标'
    session.workspace.scene_cards[0].version += 1
    session.version += 1
    session = type(session).model_validate(store.save(session, expected_version=session.version - 1))
    preview = preview_structure(graph,session,'card')
    connection = store._connection
    class FailReceipt:
        def __getattr__(self,name):
            return getattr(connection,name)
        def execute(self,sql,args=()):
            if sql.startswith('UPDATE authoring_structure_updates'):
                raise OSError('receipt disk failure')
            return connection.execute(sql,args)
    store._connection = FailReceipt()
    with pytest.raises(OSError):
        apply(graph,store,session,preview)
    count = len(graph.event_log.list())
    store._connection = connection
    apply(graph,store,session,preview)
    assert len(graph.event_log.list()) == count
    assert graph.get_node(created['scene_id']).properties['goal'] == '更新后的目标'


def test_second_scene_reuses_explicit_location_id_and_character_alias():
    graph, store, session = setup()
    first = apply(graph,store,session,preview_structure(graph,session,'card'))
    session = first['session']
    first_scene = graph.get_node(first['scene_id'])
    actor_id = first_scene.properties['pov_character_id']
    second = session.workspace.scene_cards[0].model_copy(update={'id':'second','scene_id':None,'location':first_scene.properties['location_id']})
    policy = second.writer_policy.model_dump(mode='json')
    policy['characters'][0]['public_name'] = '陌生旅人'
    second.writer_policy = type(second.writer_policy).model_validate(policy)
    session.workspace.scene_cards.append(second)
    session.version += 1
    session = type(session).model_validate(store.save(session,expected_version=session.version-1))
    preview = preview_structure(graph,session,'second')
    assert not any(n['type'] in {'Character','Location'} for n in preview['nodes'])
    assert next(n for n in preview['reuse'] if n['type']=='Location')['name'] == '车站'
    result = apply_structure(graph,store,'project',session.id,'second',session.version,second.version,preview['source_sha256'],'author','review',lambda g:None)
    assert graph.get_node(result['scene_id']).properties['location_id'] == first_scene.properties['location_id']
    assert graph.get_node(actor_id).properties['name'] == '小夏'
    assert not preview_structure(graph,result['session'],'second')['gaps']


def test_profile_projection_never_clears_canonical_style():
    graph, store, session = setup()
    from storygraph.services.project_style import resolve_project_style
    graph.seed_canon_node(node_id='style',node_type='StyleProfile',properties={'project_id':'project','pov':'第三人称','banned_patterns':['不要套话'],'rubric':['保留张力']})
    graph.update_node('project',{'style_profile_id':'style'},reviewer='author',rationale='style',source_ref='manual')
    profile = resolve_project_style(graph,'project')
    card = session.workspace.scene_cards[0]
    policy = card.writer_policy.model_dump(mode='json')
    policy.update(writer_style_origin='profile_projection',writer_style_source_profile_id='style',writer_style_source_profile_sha256=profile['sha256'])
    policy['writer_style'] = {'tone':'简洁'}
    card.writer_policy = type(card.writer_policy).model_validate(policy)
    session.version += 1
    session = type(session).model_validate(store.save(session,expected_version=session.version-1))
    preview = preview_structure(graph,session,'card')
    assert 'style_constraints' not in next(n for n in preview['nodes'] if n['type']=='Scene')['properties']
    created = apply(graph,store,session,preview)
    graph.update_node(created['scene_id'],{'style_constraints':{'banned_patterns':['场景禁令'],'rubric':['场景准则']}},reviewer='author',rationale='style',source_ref='manual')
    session = created['session']
    preview = preview_structure(graph,session,'card')
    assert 'style_constraints' not in preview['nodes'][0]['properties']
    apply(graph,store,session,preview)
    assert graph.get_node(created['scene_id']).properties['style_constraints']['banned_patterns'] == ['场景禁令']
    assert resolve_project_style(graph,'project')['banned_patterns'] == ['不要套话']


def test_explicit_author_summary_updates_plan_but_never_writer_surface():
    graph, store, session = setup()
    card = session.workspace.scene_cards[0]
    card.author_summary = '她有意留下假线索，因为幕后主使就是她。'
    session.version += 1
    session = type(session).model_validate(store.save(session,expected_version=session.version-1))
    preview = preview_structure(graph,session,'card')
    assert next(n for n in preview['nodes'] if n['type']=='Scene')['properties']['summary'] == card.author_summary
    created = apply(graph,store,session,preview)
    session = created['session']
    card = session.workspace.scene_cards[0]
    policy = resolve_card_policy(graph,store,session,card,created['scene_id'])
    assert policy.surface_plan.text == card.writer_policy.surface_plan.text
    assert card.author_summary not in policy.model_dump_json()
    card.author_summary = '她改变计划，把假线索交给另一人。'
    card.version += 1
    session.version += 1
    session = type(session).model_validate(store.save(session,expected_version=session.version-1))
    preview = preview_structure(graph,session,'card')
    assert any(c['field']=='summary' and c['after']==card.author_summary for c in preview['changes'])
    apply(graph,store,session,preview)
    assert graph.get_node(created['scene_id']).properties['summary'] == card.author_summary
    card = session.workspace.scene_cards[0]
    card.author_summary = ''
    session.version += 1
    session = type(session).model_validate(store.save(session,expected_version=session.version-1))
    assert 'summary' not in preview_structure(graph,session,'card')['nodes'][0]['properties']
