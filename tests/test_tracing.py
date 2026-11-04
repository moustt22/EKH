from app.workflows.tracing import assistant_trace, emit_trace


def test_trace_names_the_model_and_source_documents():
    trace = assistant_trace(
        "openai/gpt-4.1-mini",
        [{"document_id": "doc-1"}, {"document_id": "doc-1"}, {"document_id": "doc-2"}],
    )
    assert trace == {
        "name": "ekh.assistant",
        "model": "openai/gpt-4.1-mini",
        "source_document_ids": ["doc-1", "doc-2"],
    }


def test_tracing_stays_quiet_until_it_is_enabled(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("LangSmith client was constructed")

    monkeypatch.setattr("langsmith.Client", explode)
    emit_trace({"name": "ekh.assistant", "model": "openai/gpt-4.1-mini", "source_document_ids": ["doc-1"]})


def test_enabled_trace_sends_model_and_sources(monkeypatch):
    class Settings:
        langsmith_tracing = True
        langsmith_api_key = "test-key"
        langsmith_project = "ekh"

    class FakeClient:
        runs = []

        def __init__(self, api_key=None):
            self.api_key = api_key

        def create_run(self, **kwargs):
            FakeClient.runs.append(kwargs)

    monkeypatch.setattr("app.workflows.tracing.get_settings", lambda: Settings())
    monkeypatch.setattr("langsmith.Client", FakeClient)
    emit_trace({"name": "ekh.assistant", "model": "openai/gpt-4.1-mini", "source_document_ids": ["doc-1"]})
    assert FakeClient.runs[0]["inputs"]["model"] == "openai/gpt-4.1-mini"
    assert FakeClient.runs[0]["outputs"]["source_document_ids"] == ["doc-1"]
    assert FakeClient.runs[0]["project_name"] == "ekh"
