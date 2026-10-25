from threading import Event

from fastapi.testclient import TestClient

from apps.api import main
from storygraph.core.config import StoryGraphSettings
from test_longform_planning import Provider


def test_backend_shutdown_finishes_current_checkpoint_without_starting_another_call(tmp_path, monkeypatch):
    entered, released = Event(), Event()

    class BlockingProvider(Provider):
        def generate(self, request):
            entered.set()
            assert released.wait(5), "test provider was not released"
            return super().generate(request)

    provider = BlockingProvider()
    provider.chapters_per_volume = provider.scenes_per_chapter = 1
    settings = StoryGraphSettings(tmp_path)
    settings.llm_base_url = "https://synthetic.invalid"
    settings.llm_api_key = "synthetic-never-used"
    settings.llm_model = "fixture-model"
    monkeypatch.setattr(main, "create_llm_provider", lambda _: provider)
    app = main.create_app(settings)
    try:
        with TestClient(app) as client:
            project = client.post("/projects", json={"title": "退出时的合成规划"}).json()["project_id"]
            response = client.post(f"/projects/{project}/planning-runs", json={
                "instruction": "创建合成规划。", "target_length": 10000, "volume_count": 1,
                "chapters_per_volume": 1, "scenes_per_chapter": 1, "max_calls": 4,
            })
            assert response.status_code == 200
            run_id = response.json()["run"]["id"]
            assert entered.wait(3)
        released.set()
        app.state.planning_futures[run_id].result(timeout=5)
        run = app.state.planning_run_service.get(project, run_id)
        assert run.status == "paused" and run.stop_requested
        assert run.calls_reserved == 1 and len(provider.calls) == 1
        assert run.steps[0].proposal_ref is not None
        assert run.pending_call is None
    finally:
        released.set()
