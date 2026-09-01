import rag.agent.llm as llm_module


def test_deepseek_chat_model_has_bounded_output(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_module, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr(llm_module, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(llm_module, "DEEPSEEK_MAX_TOKENS", 1200)
    monkeypatch.setattr(llm_module, "get_llm_api_key", lambda: "test-key")

    llm_module.create_chat_model()

    assert captured["max_tokens"] == 1200
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
