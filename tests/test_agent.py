from assistant.agent import REFUSAL, answer


def test_an_empty_index_produces_the_refusal_without_calling_the_model(monkeypatch):
    monkeypatch.setattr("assistant.agent.retrieve", lambda *args, **kwargs: [])

    def explode(*args, **kwargs):
        raise AssertionError("the model must not be called with no context")

    monkeypatch.setattr("assistant.agent._invoke", explode)

    result = answer("anything at all")

    assert result.text == REFUSAL
    assert result.citations == []
