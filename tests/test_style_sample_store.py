import json
import sqlite3

from storygraph.core.time import utc_now
from storygraph.models.style import StyleSample
from storygraph.stores.style_sample_store import SQLiteStyleSampleStore


def test_style_sample_store_persists_and_ranks_matches(tmp_path):
    store_path = tmp_path / "style.sqlite"
    first = SQLiteStyleSampleStore(store_path)
    first.add(
        StyleSample(
            id="style_b",
            project_id="project_001",
            language="en-US",
            text="Warm pastoral narration with long reflective sentences.",
            source_ref="author_style:b",
            pov="third-person limited",
            tone="warm",
            dialogue_style="lyrical",
            tags=["pastoral"],
            created_at=utc_now(),
        )
    )
    first.add(
        StyleSample(
            id="style_zh_same_project",
            project_id="project_001",
            language="zh-CN",
            text="Cold restrained tower prose in the wrong language.",
            source_ref="author_style:zh",
            tone="cold and restrained",
            created_at=utc_now(),
        )
    )
    first.add(
        StyleSample(
            id="style_a",
            project_id="project_001",
            language="en-US",
            text="Cold restrained tower prose with short subtext dialogue.",
            source_ref="author_style:a",
            pov="third-person limited",
            tone="cold and restrained",
            dialogue_style="short lines with subtext",
            tags=["tower"],
            created_at=utc_now(),
        )
    )
    first.add(
        StyleSample(
            id="style_other_project",
            project_id="project_002",
            language="en-US",
            text="Cold restrained tower prose in the wrong project.",
            source_ref="author_style:other",
            pov="third-person limited",
            tone="cold and restrained",
            created_at=utc_now(),
        )
    )
    first.close()

    second = SQLiteStyleSampleStore(store_path)
    matches = second.search(
        project_id="project_001",
        language="en-US",
        query="tower conflict cold restrained short dialogue",
        pov="third-person limited",
        tone="cold and restrained",
        dialogue_style="short lines with subtext",
        tags=["tower"],
    )

    assert [match.sample.id for match in matches] == ["style_a", "style_b"]
    assert matches[0].score > matches[1].score
    assert "style_other_project" not in [match.sample.id for match in matches]
    assert "style_zh_same_project" not in [match.sample.id for match in matches]


def test_legacy_style_sample_is_readable_but_excluded_from_language_search(tmp_path):
    path = tmp_path / "legacy-style.sqlite"
    now = utc_now()
    payload = {
        "contract_version": "style_sample_v1",
        "id": "style_legacy",
        "project_id": "project_001",
        "text": "Legacy unlabeled prose.",
        "source_ref": "author_style:legacy",
        "tags": [],
        "created_at": now,
    }
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE style_samples (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_ref TEXT NOT NULL,
          pov TEXT, tone TEXT, dialogue_style TEXT, created_at TEXT NOT NULL,
          payload_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO style_samples VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            payload["id"],
            payload["project_id"],
            payload["source_ref"],
            None,
            None,
            None,
            now,
            json.dumps(payload),
        ),
    )
    connection.commit()
    connection.close()

    store = SQLiteStyleSampleStore(path)
    legacy = store.get("style_legacy")
    assert legacy.language is None
    assert legacy.language_inferred is True
    assert store.search(project_id="project_001", language="en-US", query="legacy") == []
