from core import pipeline


def test_detect_state_does_not_treat_preposition_in_as_indiana():
    assert pipeline.detect_state("a clinic in Chicago") is None
    assert pipeline.detect_state("a clinic in Indiana") == "IN"
    assert pipeline.detect_state("a clinic in IN") == "IN"


def test_detect_language_filter_from_query():
    assert pipeline.detect_language_filter("legal help in Arabic") == "arabic"
    assert pipeline.detect_language_filter("dental care") is None


def test_search_returns_grounded_source_ids_and_retrieval_mode():
    result = pipeline.search_resources(
        "dental 60629",
        use_llm=False,
        use_semantic=False,
        limit=2,
    )
    assert result["retrieval"]["mode"] == "lexical"
    assert len(result["retrieval"]["source_ids"]) == len(result["results"])
    assert all(source_id.startswith("IL:") for source_id in result["retrieval"]["source_ids"])
