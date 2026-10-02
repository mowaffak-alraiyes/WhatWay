import json

from core import retrieval


def _reset_cache():
    retrieval._EMBEDDING_CACHE.clear()
    retrieval._LOADED_CACHE_MODELS.clear()


def test_embedding_cache_round_trip_omits_queries(tmp_path, monkeypatch):
    cache = tmp_path / "embeddings.json"
    monkeypatch.setenv("WHATWAY_EMBEDDING_CACHE", str(cache))
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "test-embed")
    _reset_cache()

    retrieval._EMBEDDING_CACHE[("test-embed", "public-record-hash")] = [0.1, 0.2]
    retrieval._save_disk_cache("test-embed")

    payload = json.loads(cache.read_text())
    assert payload == {
        "version": 1,
        "model": "test-embed",
        "vectors": {"public-record-hash": [0.1, 0.2]},
    }
    assert "query" not in cache.read_text().lower()

    _reset_cache()
    retrieval._load_disk_cache("test-embed")
    assert retrieval._EMBEDDING_CACHE[("test-embed", "public-record-hash")] == [0.1, 0.2]


def test_embedding_cache_ignores_other_models(tmp_path, monkeypatch):
    cache = tmp_path / "embeddings.json"
    cache.write_text(json.dumps({
        "version": 1,
        "model": "old-model",
        "vectors": {"hash": [0.5]},
    }))
    monkeypatch.setenv("WHATWAY_EMBEDDING_CACHE", str(cache))
    _reset_cache()

    retrieval._load_disk_cache("new-model")
    assert retrieval._EMBEDDING_CACHE == {}
