from assistant.agent import GENERATE_NODE, REFUSAL, LLMCall, answer
from assistant.config import get_settings
from assistant.prompts import ANSWER_PROMPTS
from assistant.search import Hit


def test_an_empty_index_produces_the_refusal_without_calling_the_model(monkeypatch):
    monkeypatch.setattr("assistant.agent.retrieve", lambda *args, **kwargs: [])

    def explode(*args, **kwargs):
        raise AssertionError("the model must not be called with no context")

    monkeypatch.setattr("assistant.agent._invoke", explode)

    result = answer("anything at all")

    assert result.text == REFUSAL
    assert result.citations == []


def test_the_configured_answer_prompt_is_the_one_that_generates(monkeypatch, request):
    request.addfinalizer(get_settings.cache_clear)
    monkeypatch.setenv("ANSWER_PROMPT", "B")
    get_settings.cache_clear()
    hit = Hit(id="c1", citation="owner/repo#1", title="T", url="https://example.com", text="body")
    monkeypatch.setattr("assistant.agent.retrieve", lambda *args, **kwargs: [hit])
    sent = []

    def capture(node, prompt):
        sent.append((node, prompt))
        call = LLMCall(node=node, model="m", prompt_tokens=1, completion_tokens=1, latency_ms=1)
        return "YES: the context answers it", call

    monkeypatch.setattr("assistant.agent._invoke", capture)

    answer("what changed")

    generated = [prompt for node, prompt in sent if node == GENERATE_NODE]
    expected = ANSWER_PROMPTS["B"].format(question="what changed", context="[owner/repo#1] body")
    assert generated == [expected]
