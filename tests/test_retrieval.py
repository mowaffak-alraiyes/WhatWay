from core import retrieval


ITEMS = [
    {
        "id": "dental-il",
        "name": "Neighborhood Dental Center",
        "state": "IL",
        "zip_code": "60629",
        "services": ["dental"],
        "services_text": "Dental exams and oral health care",
        "languages": ["english", "spanish"],
    },
    {
        "id": "legal-il",
        "name": "Welcome Legal Aid",
        "state": "IL",
        "zip_code": "60640",
        "services": ["immigration_law"],
        "services_text": "Immigration and asylum legal services",
        "languages": ["english", "arabic"],
    },
    {
        "id": "dental-in",
        "name": "Indiana Family Dentistry",
        "state": "IN",
        "zip_code": "46201",
        "services": ["dental"],
        "services_text": "Family dental clinic",
        "languages": ["english"],
    },
]


def test_hard_metadata_filters_run_before_ranking():
    result = retrieval.retrieve(
        ITEMS,
        "dental care",
        state="IL",
        language="spanish",
        use_semantic=False,
    )
    assert [item["id"] for item in result.items] == ["dental-il"]
    assert result.mode == "lexical"


def test_zip_and_service_rank_the_matching_record_first():
    result = retrieval.retrieve(
        ITEMS,
        "family clinic",
        zip_code="46201",
        service="dental",
        use_semantic=False,
    )
    assert result.items[0]["id"] == "dental-in"
    assert result.source_ids[0] == "IN:dental-in"
    assert result.items[0]["source_id"] == "IN:dental-in"


def test_source_verification_date_is_grounded_in_record_notes():
    item = dict(ITEMS[0], notes="HRSA source - Last reviewed April 2025")
    result = retrieval.retrieve([item], "dental", use_semantic=False)
    assert result.items[0]["last_verified"] == "April 2025"
    assert result.items[0]["source_id"] == result.source_ids[0]


def test_semantic_failure_falls_back_to_lexical(monkeypatch):
    monkeypatch.setattr(retrieval, "_semantic_scores", lambda *_: None)
    result = retrieval.retrieve(ITEMS, "asylum help", use_semantic=True)
    assert result.items[0]["id"] == "legal-il"
    assert result.semantic_available is False


def test_semantic_scores_can_improve_conversational_recall(monkeypatch):
    monkeypatch.setattr(retrieval, "_semantic_scores", lambda *_: [0.95, 0.0, 0.1])
    result = retrieval.retrieve(ITEMS, "my tooth hurts", use_semantic=True)
    assert result.items[0]["id"] == "dental-il"
    assert result.mode == "hybrid"
