from core import ollama


def test_native_url_strips_only_openai_suffix(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.org/v1")
    assert ollama.openai_base_url() == "https://ollama.example.org/v1"
    assert ollama.native_base_url() == "https://ollama.example.org"


def test_non_http_ollama_url_is_rejected(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "file:///tmp/not-an-origin")
    try:
        ollama.native_base_url()
    except ValueError as error:
        assert "http(s)" in str(error)
    else:
        raise AssertionError("unsafe Ollama URL was accepted")


def test_private_origin_headers(monkeypatch):
    monkeypatch.setenv("OLLAMA_AUTH_TOKEN", "bearer-secret")
    monkeypatch.setenv("OLLAMA_CF_ACCESS_CLIENT_ID", "access-id")
    monkeypatch.setenv("OLLAMA_CF_ACCESS_CLIENT_SECRET", "access-secret")
    assert ollama.native_headers(json_content=True) == {
        "CF-Access-Client-Id": "access-id",
        "CF-Access-Client-Secret": "access-secret",
        "Content-Type": "application/json",
        "Authorization": "Bearer bearer-secret",
    }
    assert ollama.access_headers() == {
        "CF-Access-Client-Id": "access-id",
        "CF-Access-Client-Secret": "access-secret",
    }


def test_access_headers_require_complete_pair(monkeypatch):
    monkeypatch.setenv("OLLAMA_CF_ACCESS_CLIENT_ID", "access-id")
    monkeypatch.delenv("OLLAMA_CF_ACCESS_CLIENT_SECRET", raising=False)
    assert ollama.access_headers() == {}
