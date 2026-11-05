import pytest
from google.genai import types

from vinyl_agents.exceptions import LlmError
from vinyl_agents.llm.gemini import GeminiClient
from vinyl_agents.llm.schemas import Message, ToolCall, ToolResult
from vinyl_agents.tools.vinyl_tools import RateAlbumTool


@pytest.fixture
def gemini(settings):
    settings.gemini_api_key = "test-key"
    return GeminiClient(settings)


def test_requires_api_key(settings):
    with pytest.raises(LlmError):
        GeminiClient(settings)


def test_tool_schema_is_accepted_by_the_sdk(gemini):
    spec = RateAlbumTool(None).spec()
    declaration = gemini._declaration(spec)
    assert declaration.name == "rate_album"
    assert declaration.parameters_json_schema["properties"]["rating"]["maximum"] == 10
    assert "title" not in declaration.parameters_json_schema


def test_function_call_response_is_converted(gemini):
    response = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part.from_function_call(name="add_album", args={"album_id": "a1"})]))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=189, candidates_token_count=22, total_token_count=211))
    result = gemini._to_response(response)
    assert result.tool_calls == [ToolCall(name="add_album", args={"album_id": "a1"})]
    assert (result.usage.prompt_tokens, result.usage.completion_tokens, result.usage.total_tokens) == (189, 22, 211)
    assert gemini._to_content(Message(role="model", provider_payload=result.provider_payload)) is result.provider_payload


def test_tool_results_become_function_response_parts(gemini):
    content = gemini._to_content(Message(role="tool", tool_results=[ToolResult(name="add_album", result={"ok": True})]))
    assert content.role == "user" and content.parts[0].function_response.name == "add_album"


async def test_overloaded_model_is_retried(gemini, monkeypatch):
    from google.genai import errors
    ok = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text="hi")]))])
    calls = []

    async def fake_generate(**kwargs):
        calls.append(1)
        if len(calls) < 3:
            raise errors.ServerError(503, {"error": {"message": "high demand"}})
        return ok

    async def no_sleep(_):
        return None

    monkeypatch.setattr(gemini._client.aio.models, "generate_content", fake_generate)
    monkeypatch.setattr("vinyl_agents.llm.gemini.asyncio.sleep", no_sleep)
    result = await gemini.generate("s", [Message.user("x")], [], 32)
    assert result.text == "hi" and len(calls) == 3
