from pgvector import Vector

from assistant.agent import REFUSAL, answer
from assistant.config import get_settings
from assistant.embed import embed_texts
from assistant.prompts import ANSWER_PROMPTS
from assistant.search import Hit

GRADE_PASSES = "YES: the context answers it"


class FakeResponse:
    """What ChatOpenAI.invoke returns: the message content, and the usage a call is costed from."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.usage_metadata = {"input_tokens": 1, "output_tokens": 1}


class FakeModel:
    """Stands in for the ChatOpenAI client, the one network edge testing.md allows stubbing."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def __call__(self) -> "FakeModel":
        """agent._model() hands back the client, so this hands back itself and stays one object."""
        return self

    def invoke(self, prompt: str) -> FakeResponse:
        """Record what was asked and answer with the canned reply, as the real client would."""
        self.prompts.append(prompt)
        return FakeResponse(self.reply)


def test_an_empty_index_produces_the_refusal_without_calling_the_model(conn, monkeypatch):
    model = FakeModel(GRADE_PASSES)
    monkeypatch.setattr("assistant.agent._model", model)

    result = answer("anything at all")

    assert result.text == REFUSAL
    assert result.citations == []
    assert model.prompts == []


def test_the_configured_answer_prompt_is_the_one_that_generates(conn, monkeypatch, request):
    request.addfinalizer(get_settings.cache_clear)
    monkeypatch.setenv("ANSWER_PROMPT", "B")
    get_settings.cache_clear()
    hit = Hit(id="c1", citation="owner/repo#1", title="T", url="https://example.com", text="body")
    conn.execute(
        "INSERT INTO chunks (id, repo, source_type, title, url, citation, text, embedding)"
        " VALUES (%s, 'owner/repo', 'issue', %s, %s, %s, %s, %s)",
        (hit.id, hit.title, hit.url, hit.citation, hit.text, Vector(embed_texts([hit.text])[0])),
    )
    conn.commit()
    model = FakeModel(GRADE_PASSES)
    monkeypatch.setattr("assistant.agent._model", model)

    answer("what changed")

    context = f"[{hit.citation}] {hit.text}"
    assert ANSWER_PROMPTS["B"].format(question="what changed", context=context) in model.prompts
    assert ANSWER_PROMPTS["A"].format(question="what changed", context=context) not in model.prompts
