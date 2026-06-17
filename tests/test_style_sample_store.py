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
            id="style_a",
            project_id="project_001",
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
        query="tower conflict cold restrained short dialogue",
        pov="third-person limited",
        tone="cold and restrained",
        dialogue_style="short lines with subtext",
        tags=["tower"],
    )

    assert [match.sample.id for match in matches] == ["style_a", "style_b"]
    assert matches[0].score > matches[1].score
    assert "style_other_project" not in [match.sample.id for match in matches]

