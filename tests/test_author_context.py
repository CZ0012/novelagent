"""Local author context, isolated title lifecycle, and exact durable search."""
import json
import pytest
from storygraph.core.errors import ContractError
from storygraph.services.authoring import AuthoringService
from storygraph.services.llm_provider import LLMResponse
from storygraph.stores.authoring_store import SQLiteAuthoringStore
from storygraph.stores.author_context import AuthorContextStore
from storygraph.stores.proposal_store import SQLiteProposalStore


@pytest.fixture
def setup_context(tmp_path):
    proposals = SQLiteProposalStore(tmp_path / "proposals.db")
    sessions = SQLiteAuthoringStore(proposals)
    service = AuthoringService(store=sessions)
    session = service.create(project_id="p",content_language="zh-CN",title="最初标题",idea="我偏爱克制的对白，真相暂不决定。")
    return proposals,sessions,service,session,AuthorContextStore(sessions)


def test_instructions_versions_and_scopes(setup_context):
    _,_,_,_,context = setup_context
    assert context.context("p")["version"] == 0
    assert context.instructions("p","使用克制的对白",0)["version"] == 1
    assert context.context("other")["instructions"] == ""
    with pytest.raises(ContractError,match="stale"):
        context.instructions("p","覆盖",0)


def test_memory_provenance_and_manual_tombstone_survive_replay(setup_context):
    proposals,sessions,_,session,context = setup_context
    memory = dict(text="偏爱克制的对白",kind="preference",status="active",source_message_id=session.messages[0].id,evidence="偏爱克制的对白")
    with pytest.raises(ContractError,match="evidence"):
        context.record("p",session.id,**{**memory,"source_message_id":"assistant"})
    with pytest.raises(ContractError):
        context.record("other",session.id,**memory)
    value = context.record("p",session.id,**memory)
    edited = context.edit("p",value["id"],expected_version=1,text="撤回这条偏好",status="withdrawn")
    restarted = AuthorContextStore(SQLiteAuthoringStore(proposals))
    assert restarted.record("p",session.id,**memory) == edited
    assert restarted.record("p",session.id,**{**memory,"evidence":"我偏爱克制的对白"}) == edited
    assert restarted.memories("p")["records"] == []
    assert restarted.memories("p",include_withdrawn=True)["records"][0]["version"] == 2


def test_title_manual_wins_inflight_and_no_restart_repeat(setup_context):
    proposals,sessions,_,session,context = setup_context
    context.initialize_title(session,automatic=True)
    calls = []
    def generate(*args):
        calls.append(args)
        context.rename("p",session.id,"作者手动标题",expected_version=1)
        return "模型标题"
    context.generate_title("p",session.id,generate,lambda _:"zh-CN")
    assert context.title("p",session.id)["title"] == "作者手动标题"
    AuthorContextStore(SQLiteAuthoringStore(proposals)).generate_title("p",session.id,generate,lambda _:"zh-CN")
    assert len(calls) == 1
    assert sessions.get("p",session.id)["version"] == 1


def test_title_failure_and_language_change_do_not_retry(setup_context):
    _,_,_,session,context = setup_context
    context.initialize_title(session,automatic=True)
    calls = []
    context.generate_title("p",session.id,lambda *args:calls.append(args),lambda _:"en-US")
    assert calls == []
    assert context.title("p",session.id)["state"] == "failed"
    context.generate_title("p",session.id,lambda *args:calls.append(args),lambda _:"zh-CN")
    assert calls == []


def test_project_search_pagination_and_aged_out_message(setup_context):
    _,sessions,service,session,context = setup_context
    from storygraph.services.authoring import _message
    for i in range(45):
        session.messages.append(_message("author",f"检索词{i}"))
    session.version += 1
    sessions.save(session,expected_version=1)
    assert len(sessions.get("p",session.id)["messages"]) == 40
    page = context.search("p","检索词",limit=10)
    assert page["total_matches"] == 45 and page["next_offset"] == 10
    assert context.search("p","检索词",offset=40,limit=10)["more"] is False
    exact = context.search("p","检索词0")["records"][0]
    assert exact["session_id"] == session.id and exact["position"] == 1
    assert context.search("other","检索词")["records"] == []
    assert context.session_page("p","最初")["total_matches"] == 1


def test_finish_records_memories_in_normal_main_call(setup_context):
    _,sessions,_,session,context = setup_context
    class Provider:
        calls = 0
        def generate(self,request):
            self.calls += 1
            assert "author_only_project_context" in request.messages[1].content
            return LLMResponse(json.dumps({"tool":"finish","args":{"message":"我会保留你的对白偏好，真相继续保持未定。","author_memories":[{"text":"偏爱克制的对白","kind":"preference","status":"active","source_message_id":session.messages[0].id,"evidence":"偏爱克制的对白"}]}},ensure_ascii=False))
    provider = Provider()
    service = AuthoringService(store=sessions,provider=provider,model="fake")
    service.turn(project_id="p",session_id=session.id,expected_version=1,message="继续讨论。")
    assert provider.calls == 1
    assert context.memories("p")["records"][0]["source_message_id"] == session.messages[0].id


def test_normal_discussion_retracts_tentative_memory_across_sessions(setup_context):
    _,sessions,service,initial,context = setup_context
    old = context.record("p",initial.id,text="真相暂不决定",kind="tentative",status="tentative",source_message_id=initial.messages[0].id,evidence="真相暂不决定")
    fresh = service.create(project_id="p",content_language="zh-CN",title="新讨论",idea="我决定撤回以前真相暂不决定的灵感，确定采用另一种真相。")
    class Provider:
        def generate(self,request):
            assert old["id"] in request.messages[1].content
            return LLMResponse(json.dumps({"tool":"finish","args":{"message":"已撤回以前的待定灵感。","author_memories":[{"operation":"withdraw","memory_id":old["id"],"text":"撤回以前的灵感","kind":"tentative","status":"tentative","source_message_id":fresh.messages[0].id,"evidence":"我决定撤回以前真相暂不决定的灵感"}]}},ensure_ascii=False))
    service = AuthoringService(store=sessions,provider=Provider(),model="fake")
    service.turn(project_id="p",session_id=fresh.id,expected_version=1,message="请撤回那条记忆。")
    assert context.memories("p")["records"] == []
    tombstone = context.memories("p",include_withdrawn=True)["records"][0]
    assert tombstone["withdrawal"]["source_session_id"] == fresh.id
    assert context.record("p",initial.id,text="真相暂不决定",kind="tentative",status="tentative",source_message_id=initial.messages[0].id,evidence="真相暂不决定")["status"] == "withdrawn"


def test_unrelated_memories_and_invalid_optional_memory_do_not_pollute_or_discard_reply(setup_context):
    _,sessions,service,initial,context = setup_context
    unrelated = service.create(project_id="p",content_language="zh-CN",title="private",idea="我偏爱晨跑，不向别人提起家庭隐情。")
    context.record("p",unrelated.id,text="家庭隐情_CANARY",kind="preference",status="active",source_message_id=unrelated.messages[0].id,evidence="不向别人提起家庭隐情")
    class Provider:
        calls = 0
        def generate(self,request):
            self.calls += 1
            assert "家庭隐情_CANARY" not in request.messages[1].content
            return LLMResponse(json.dumps({"tool":"finish","args":{"message":"我们继续讨论对白。","author_memories":[{"source_message_id":"assistant","text":"伪造"},42]}},ensure_ascii=False))
    provider = Provider()
    result = AuthoringService(store=sessions,provider=provider,model="fake").turn(project_id="p",session_id=initial.id,expected_version=1,message="讨论对白。")
    assert provider.calls == 1 and result.turn_status == "idle"
    assert any(m.role == "assistant" and m.content == "我们继续讨论对白。" for m in result.messages)
    assert result.messages[-1].tool_name == "author_memory_validation"
    assert len(context.memories("p")["records"]) == 1


def test_manual_form_opened_before_auto_title_completion_still_wins(setup_context):
    _,_,_,session,context = setup_context
    context.initialize_title(session,automatic=True)
    form_version = context.title("p",session.id)["version"]
    context.generate_title("p",session.id,lambda *_:"自动新标题",lambda _:"zh-CN")
    assert context.title("p",session.id)["version"] == form_version + 1
    manual = context.rename("p",session.id,"表单中输入的手动标题",form_version)
    assert manual["origin"] == "manual" and manual["title"] == "表单中输入的手动标题"
    with pytest.raises(ContractError,match="stale"):
        context.rename("p",session.id,"另一个旧手动表单",form_version)
    with pytest.raises(ContractError,match="stale"):
        context.rename("p",session.id,"只差一个版本的旧手动表单",manual["version"]-1)


def test_withdrawn_author_source_projected_out_of_main_history(setup_context):
    _,sessions,_,session,context = setup_context
    memory = context.record("p",session.id,text="偏爱克制的对白",kind="preference",status="active",source_message_id=session.messages[0].id,evidence="偏爱克制的对白")
    context.edit("p",memory["id"],expected_version=1,text="已撤回",status="withdrawn")
    # A long-running story can have more recent withdrawals for other source
    # messages. They must never push this visible message's correction out.
    with context.lock, context.db:
        for i in range(105):
            other = dict(memory, id=f"other-{i}", source_message_id=f"later-message-{i}",
                         status="withdrawn", edited_by="author", version=2)
            context.db.execute("INSERT INTO author_memories VALUES (?,?,?,?,?)",
                               ("p", other["id"], 2, json.dumps(other), f"other-evidence-{i}"))
    class Provider:
        def generate(self,request):
            assert all("我偏爱克制的对白" not in message.content for message in request.messages)
            assert any("superseded notebook source" in message.content for message in request.messages)
            return LLMResponse(json.dumps({"tool":"finish","args":{"message":"继续讨论新的方向。"}},ensure_ascii=False))
    AuthoringService(store=sessions,provider=Provider(),model="fake").turn(project_id="p",session_id=session.id,expected_version=1,message="换个新方向。")
    assert context.message("p",session.id,session.messages[0].id)["message"]["content"] == session.messages[0].content
