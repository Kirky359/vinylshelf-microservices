import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpDemoClient:
    """A minimal MCP host: starts the server as a subprocess (stdio), lists its capabilities and calls a few tools.
    Useful for checking the server without Claude Desktop or the MCP Inspector."""

    def __init__(self, album_id: str = "a3", tracks: int = 9):
        self._params = StdioServerParameters(command=sys.executable, args=["-m", "vinyl_agents.task2_mcp_server"],
                                       env=dict(os.environ))  # stdio passes only a few variables unless env is given
        self._album_id, self._tracks = album_id, tracks

    async def run(self) -> None:
        async with stdio_client(self._params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            print("🧰 tools:     ", [t.name for t in (await session.list_tools()).tools])
            print("📚 resources: ", [str(r.uri) for r in (await session.list_resources()).resources],
                  [r.uriTemplate for r in (await session.list_resource_templates()).resourceTemplates])
            print("📝 prompts:   ", [p.name for p in (await session.list_prompts()).prompts])
            calls = [("search_catalog", {"q": "soul"}), ("add_album", {"album_id": self._album_id}),
                     ("add_album", {"album_id": "../etc/passwd"}),  # rejected by argument validation
                     ("rate_album", {"album_id": self._album_id, "rating": 11}),  # rejected: 1..10
                     ("update_progress", {"album_id": self._album_id, "tracks_played": self._tracks}),
                     ("complete_album", {"album_id": self._album_id}), ("get_dashboard", {})]
            for name, args in calls:
                result = await session.call_tool(name, args)
                text = result.content[0].text if result.content else ""
                print(f"\n🔧 {name}({json.dumps(args)}) -> {'ERROR' if result.isError else 'ok'}")
                print("   " + text.replace("\n", " ")[:260])
            album = await session.read_resource(f"vinylshelf://catalog/{self._album_id}")
            print("\n📖 resource vinylshelf://catalog/" + self._album_id, "->", album.contents[0].text[:120])


if __name__ == "__main__":
    asyncio.run(McpDemoClient().run())
