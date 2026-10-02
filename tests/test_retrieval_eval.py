from evals.run_retrieval_eval import run


def test_retrieval_eval_reports_filter_and_source_failures(monkeypatch):
    monkeypatch.setattr(
        "evals.run_retrieval_eval.search_resources",
        lambda *args, **kwargs: {
            "retrieval": {"mode": "lexical", "source_ids": ["IL:wrong"]},
            "results": [{"state": "IL", "languages": ["english"]}],
        },
    )
    report = run(
        [{
            "name": "failure",
            "query": "help in Arabic",
            "expected_source_ids": ["IL:expected"],
            "expected_state": "IL",
            "expected_language": "arabic",
        }],
        semantic=False,
    )
    assert report["passed"] == 0
    assert report["cases"][0]["checks"] == {
        "expected_id_in_top_3": False,
        "state_filter": True,
        "language_filter": False,
    }
