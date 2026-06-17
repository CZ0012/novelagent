from apps.cli.main import run_review_demo


def test_review_demo_accept_commits_candidate_fact():
    result = run_review_demo(action="accept", reviewer="editor", note="Looks right.")

    assert result["candidate"]["status"] == "ACCEPTED_FOR_CANON"
    assert result["candidate"]["review"]["status"] == "accepted"
    assert result["candidate"]["review"]["reviewer"] == "editor"
    assert result["candidate"]["review"]["note"] == "Looks right."
    assert result["pending_count"] == 0
    assert result["committed_relations"]


def test_review_demo_defer_keeps_fact_out_of_canon():
    result = run_review_demo(action="defer")

    assert result["candidate"]["status"] == "DEFERRED"
    assert result["candidate"]["review"]["status"] == "deferred"
    assert result["pending_count"] == 0
    assert result["committed_relations"] == []
