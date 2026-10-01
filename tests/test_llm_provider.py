import llm_service


def _reset_provider_state():
    llm_service._ACTIVE_PROVIDER = None
    llm_service._ACTIVE_MODEL = None


def test_llm_provider_can_be_disabled(monkeypatch):
    monkeypatch.setenv("WHATWAY_LLM_PROVIDER", "none")
    _reset_provider_state()

    assert llm_service.get_llm_client() is None
    assert llm_service.llm_status()["available"] is False


def test_workers_ai_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("WHATWAY_LLM_PROVIDER", "workers_ai")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account-test")
    monkeypatch.setenv("CLOUDFLARE_AI_TOKEN", "token-test")
    monkeypatch.setenv("CLOUDFLARE_AI_MODEL", "model-test")
    _reset_provider_state()

    client = llm_service.get_llm_client()
    status = llm_service.llm_status()

    assert client is not None
    assert str(client.base_url) == (
        "https://api.cloudflare.com/client/v4/accounts/account-test/ai/v1/"
    )
    assert status["provider"] == "workers_ai"
    assert status["model"] == "model-test"
