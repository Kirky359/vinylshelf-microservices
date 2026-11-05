import json
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field, TypeAdapter

from vinyl_agents.task2_mcp_server.config import McpSettings
from vinyl_agents.task2_mcp_server.guard import McpGuard
from vinyl_agents.vinylshelf.service import UserSessionService, VinylShelfService
from vinyl_agents.vinylshelf.types import Identifier, Rating, SearchQuery, TracksPlayed, UserId

OptionalUser = Annotated[UserId | None, Field(description="user id; omit to use the user configured for the server")]

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)


class VinylShelfMcpServer:
    """The VinylShelf REST API (lab 1-3) as an MCP server: tools = actions, resources = readable data, prompts = templates."""

    def __init__(self, service: VinylShelfService, user_session: UserSessionService, guard: McpGuard,
                 settings: McpSettings):
        self._service = service
        self._user_session = user_session
        self._guard = guard
        self._settings = settings
        self.mcp = FastMCP("vinylshelf", host=settings.mcp_host, port=settings.mcp_port,
                           instructions="Manage a vinyl collection: search the catalog, add albums, track listening "
                                        "progress, complete and rate albums, read statistics.")
        self._register_tools()
        self._register_resources()
        self._register_prompts()

    def run(self) -> None:
        self.mcp.run(transport=self._settings.mcp_transport)  # "stdio" or "streamable-http"

    async def _as_user(self, user_id: str | None, use_case, *args):
        """Runs a service use case for the given user, or for the user configured for the server."""
        return await use_case(user_id or await self._user_session.ensure_user(), *args)

    # ---- tools -------------------------------------------------------------------------------------------------
    def _register_tools(self) -> None:
        mcp, guard, service = self.mcp, self._guard, self._service

        @mcp.tool(title="Search catalog", annotations=READ)
        async def search_catalog(q: SearchQuery = "") -> dict:
            """Search albums in the catalog by part of title, artist or genre (empty = all)."""
            return await guard.run("search_catalog", False, lambda: service.search_catalog(q))

        @mcp.tool(title="Get collection", annotations=READ)
        async def get_collection(user_id: OptionalUser = None) -> dict:
            """List the albums of a user's collection with status and progress."""
            return await guard.run("get_collection", False, lambda: self._as_user(user_id, service.get_collection))

        @mcp.tool(title="Add album", annotations=WRITE)
        async def add_album(album_id: Identifier, user_id: OptionalUser = None) -> dict:
            """Add a catalog album to the collection (status Planned)."""
            return await guard.run("add_album", True, lambda: self._as_user(user_id, service.add_album, album_id))

        @mcp.tool(title="Update listening progress", annotations=WRITE)
        async def update_progress(album_id: Identifier, tracks_played: TracksPlayed, user_id: OptionalUser = None) -> dict:
            """Set the number of played tracks of an album (moves it to Listening)."""
            return await guard.run("update_progress", True, lambda: self._as_user(user_id, service.update_progress, album_id, tracks_played))

        @mcp.tool(title="Complete album", annotations=WRITE)
        async def complete_album(album_id: Identifier, user_id: OptionalUser = None) -> dict:
            """Complete an album (all tracks must be played). Runs a SAGA and returns its final state:
            processed = completed, compensated = rolled back by the coordinator."""
            return await guard.run("complete_album", True, lambda: self._as_user(user_id, service.complete_album, album_id))

        @mcp.tool(title="Rate album", annotations=WRITE)
        async def rate_album(album_id: Identifier, rating: Rating, user_id: OptionalUser = None) -> dict:
            """Rate an album 1-10 (the album must be Listening or Completed)."""
            return await guard.run("rate_album", True, lambda: self._as_user(user_id, service.rate_album, album_id, rating))

        @mcp.tool(title="Get dashboard", annotations=READ)
        async def get_dashboard(user_id: OptionalUser = None) -> dict:
            """Listening statistics built by the analytics consumer."""
            return await guard.run("get_dashboard", False, lambda: self._as_user(user_id, service.get_dashboard))

    # ---- resources ---------------------------------------------------------------------------------------------
    def _register_resources(self) -> None:
        mcp, guard, service = self.mcp, self._guard, self._service

        @mcp.resource("vinylshelf://catalog", mime_type="application/json")
        async def catalog() -> str:
            """The whole album catalog."""
            return json.dumps(await guard.run("resource:catalog", False, lambda: service.search_catalog("")))

        @mcp.resource("vinylshelf://catalog/{album_id}", mime_type="application/json")
        async def catalog_album(album_id: str) -> str:
            """One album of the catalog."""
            self._validate_id(album_id)
            return json.dumps(await guard.run("resource:album", False, lambda: service.get_album(album_id)))

        @mcp.resource("vinylshelf://users/{user_id}/collection", mime_type="application/json")
        async def user_collection(user_id: str) -> str:
            """Collection of a user."""
            self._validate_id(user_id)
            return json.dumps(await guard.run("resource:collection", False, lambda: service.get_collection(user_id)))

        @mcp.resource("vinylshelf://users/{user_id}/dashboard", mime_type="application/json")
        async def user_dashboard(user_id: str) -> str:
            """Listening statistics of a user."""
            self._validate_id(user_id)
            return json.dumps(await guard.run("resource:dashboard", False, lambda: service.get_dashboard(user_id)))

    @staticmethod
    def _validate_id(value: str) -> None:
        TypeAdapter(Identifier).validate_python(value)

    # ---- prompts -----------------------------------------------------------------------------------------------
    def _register_prompts(self) -> None:
        mcp = self.mcp

        @mcp.prompt(title="Recommend the next album")
        def recommend_next_album() -> str:
            return ("Look at my collection and my dashboard with the VinylShelf tools. Then pick ONE album from the "
                    "catalog that I do not own yet, matching my top genres, and explain the choice in two sentences.")

        @mcp.prompt(title="Weekly listening report")
        def listening_report() -> str:
            return ("Make a short report: albums completed, tracks played, average rating, favourite genre and "
                    "artist. Use get_dashboard and get_collection, do not change any data.")

        @mcp.prompt(title="Finish an album")
        def finish_album(album_title: str) -> str:
            return (f"Finish the album '{album_title}': find it in the catalog, add it to my collection if it is "
                    "missing, set progress to the last track, complete it and rate it 9. Report the final saga state.")
