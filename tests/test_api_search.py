from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_search_endpoint_returns_grounded_retrieval_metadata():
    response = client.post(
        "/search",
        json={
            "query": "dental 60629",
            "limit": 2,
            "use_llm": False,
            "use_semantic": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval"]["mode"] == "lexical"
    assert len(payload["results"]) == len(payload["retrieval"]["source_ids"]) == 2


def test_search_endpoint_rejects_string_boolean():
    response = client.post(
        "/search",
        json={"query": "dental", "use_semantic": "false"},
    )
    assert response.status_code == 422


def test_search_endpoint_rejects_empty_query():
    response = client.post("/search", json={"query": " "})
    assert response.status_code == 422


def test_search_openapi_exposes_validated_request_and_response_models():
    operation = client.get("/openapi.json").json()["paths"]["/search"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/SearchRequest"
    )
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/SearchResponse"
    )
