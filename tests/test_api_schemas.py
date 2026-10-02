import pytest
from pydantic import ValidationError

from api.schemas import SearchRequest, SearchResponse
from core.pipeline import search_resources


def test_search_request_normalizes_filters_and_preserves_booleans():
    payload = SearchRequest(
        query="  dental 60629  ",
        state="il",
        language="EN",
        language_filter="Spanish",
        use_llm=False,
        use_semantic=False,
    )
    assert payload.query == "dental 60629"
    assert payload.state == "IL"
    assert payload.language == "en"
    assert payload.language_filter == "spanish"
    assert payload.use_llm is False
    assert payload.use_semantic is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("query", "   "),
        ("category", "Medical"),
        ("state", "Illinois"),
        ("limit", 0),
        ("limit", 11),
    ],
)
def test_search_request_rejects_invalid_public_inputs(field, value):
    values = {"query": "dental", field: value}
    with pytest.raises(ValidationError):
        SearchRequest(**values)


def test_pipeline_output_matches_public_grounded_response():
    raw = search_resources(
        "dental 60629",
        use_llm=False,
        use_semantic=False,
        limit=2,
    )
    response = SearchResponse(**raw)
    assert response.retrieval.mode == "lexical"
    assert len(response.results) == len(response.retrieval.source_ids) == 2
    assert all(source_id.startswith("IL:") for source_id in response.retrieval.source_ids)
