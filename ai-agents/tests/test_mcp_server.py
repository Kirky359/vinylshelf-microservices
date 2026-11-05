import json
from contextlib import asynccontextmanager

from mcp.shared.memory import create_connected_server_and_client_session

from tests.conftest import make_container
from vinyl_agents.task2_mcp_server.app import McpApplication


@asynccontextmanager
async def connect(settings, backend, mcp_settings):
    """An in-memory MCP client connected to the server (the same protocol as stdio, without a subprocess)."""
    server = McpApplication(make_container(settings, backend), mcp_settings).build()
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as session:
        yield session


def text_of(result) -> str:
    return result.content[0].text


async def test_exposes_tools_resources_and_prompts(settings, backend, mcp_settings):
    async with connect(settings, backend, mcp_settings) as mcp:
        assert {t.name for t in (await mcp.list_tools()).tools} == {
            "search_catalog", "get_collection", "add_album", "update_progress", "complete_album", "rate_album",
            "get_dashboard"}
        assert len((await mcp.list_resource_templates()).resourceTemplates) == 3
        assert {p.name for p in (await mcp.list_prompts()).prompts} == {
            "recommend_next_album", "listening_report", "finish_album"}


async def test_tool_chain_through_mcp_uses_default_user(settings, backend, mcp_settings):
    async with connect(settings, backend, mcp_settings) as mcp:
        assert not (await mcp.call_tool("add_album", {"album_id": "a1"})).isError
        await mcp.call_tool("update_progress", {"album_id": "a1", "tracks_played": 5})
        done = json.loads(text_of(await mcp.call_tool("complete_album", {"album_id": "a1"})))
        assert done["saga_state"] == "processed" and done["album_status"] == "Completed"
        assert json.loads(text_of(await mcp.call_tool("get_dashboard", {})))["albums_completed"] == 1


async def test_arguments_are_validated(settings, backend, mcp_settings):
    async with connect(settings, backend, mcp_settings) as mcp:
        for tool, args in (("add_album", {"album_id": "../x"}), ("rate_album", {"album_id": "a1", "rating": 11}),
                           ("update_progress", {"album_id": "a1", "tracks_played": -1})):
            assert (await mcp.call_tool(tool, args)).isError


async def test_api_errors_become_tool_errors(settings, backend, mcp_settings):
    async with connect(settings, backend, mcp_settings) as mcp:
        result = await mcp.call_tool("add_album", {"album_id": "zzz"})
        assert result.isError and "album not found" in text_of(result)


async def test_resource_and_prompt(settings, backend, mcp_settings):
    async with connect(settings, backend, mcp_settings) as mcp:
        album = json.loads((await mcp.read_resource("vinylshelf://catalog/a2")).contents[0].text)
        assert album["title"] == "Abbey Road"
        prompt = await mcp.get_prompt("finish_album", {"album_title": "Abbey Road"})
        assert "Abbey Road" in prompt.messages[0].content.text


async def test_read_only_mode_blocks_writes(settings, backend, mcp_settings):
    mcp_settings.mcp_read_only = True
    async with connect(settings, backend, mcp_settings) as mcp:
        blocked = await mcp.call_tool("add_album", {"album_id": "a1"})
        assert blocked.isError and "read-only" in text_of(blocked)
        assert not (await mcp.call_tool("search_catalog", {"q": "jazz"})).isError
    assert ("POST", "/collection-service/collection/add") not in backend.requests


async def test_rate_limit(settings, backend, mcp_settings):
    mcp_settings.mcp_rate_limit_per_minute = 2
    async with connect(settings, backend, mcp_settings) as mcp:
        await mcp.call_tool("search_catalog", {})
        await mcp.call_tool("search_catalog", {})
        limited = await mcp.call_tool("search_catalog", {})
        assert limited.isError and "rate limit" in text_of(limited)
