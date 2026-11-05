"""LLM tools of Task 1. The current user comes from ToolContext, so the model cannot act on behalf of someone else."""
from pydantic import BaseModel

from vinyl_agents.exceptions import InvalidInput
from vinyl_agents.tools.base import StrictArgs, Tool, ToolContext
from vinyl_agents.vinylshelf.service import VinylShelfService
from vinyl_agents.vinylshelf.types import Identifier, Rating, SearchQuery, TracksPlayed


class _AlbumArgs(StrictArgs):
    album_id: Identifier


class _SearchArgs(StrictArgs):
    q: SearchQuery = ""


class _ProgressArgs(_AlbumArgs):
    tracks_played: TracksPlayed


class _RateArgs(_AlbumArgs):
    rating: Rating


class _UserTool(Tool):
    def __init__(self, service: VinylShelfService):
        self._service = service

    @staticmethod
    def _user(ctx: ToolContext) -> str:
        if not ctx.user_id:
            raise InvalidInput("no user in the session")
        return ctx.user_id


class SearchCatalogTool(_UserTool):
    name = "search_catalog"
    description = "Search albums in the catalog by part of title, artist or genre. Empty query lists everything. " \
                  "Returns id, title, artist, genre and number of tracks."
    args_model = _SearchArgs

    async def execute(self, args: _SearchArgs, ctx: ToolContext) -> dict:
        return await self._service.search_catalog(args.q)


class GetCollectionTool(_UserTool):
    name = "get_collection"
    description = "List the albums in the user's collection with status (Planned, Listening, CompletionPending, " \
                  "Completed) and listening progress."

    async def execute(self, args: BaseModel, ctx: ToolContext) -> dict:
        return await self._service.get_collection(self._user(ctx))


class AddAlbumTool(_UserTool):
    name = "add_album"
    description = "Add a catalog album to the user's collection (status Planned). Fails with 409 if it is already there."
    args_model = _AlbumArgs
    mutating = True

    async def execute(self, args: _AlbumArgs, ctx: ToolContext) -> dict:
        return await self._service.add_album(self._user(ctx), args.album_id)


class UpdateProgressTool(_UserTool):
    name = "update_progress"
    description = "Set how many tracks of an album in the collection are played (0..number of tracks). " \
                  "Moves the album to Listening."
    args_model = _ProgressArgs
    mutating = True

    async def execute(self, args: _ProgressArgs, ctx: ToolContext) -> dict:
        return await self._service.update_progress(self._user(ctx), args.album_id, args.tracks_played)


class CompleteAlbumTool(_UserTool):
    name = "complete_album"
    description = "Mark an album as completed. Allowed only when all tracks are played. Starts a distributed " \
                  "transaction (SAGA) and waits for the result: saga_state is 'processed' (ok) or 'compensated' (rolled back)."
    args_model = _AlbumArgs
    mutating = True

    async def execute(self, args: _AlbumArgs, ctx: ToolContext) -> dict:
        return await self._service.complete_album(self._user(ctx), args.album_id)


class RateAlbumTool(_UserTool):
    name = "rate_album"
    description = "Rate an album from 1 to 10. Only albums in status Listening or Completed can be rated."
    args_model = _RateArgs
    mutating = True

    async def execute(self, args: _RateArgs, ctx: ToolContext) -> dict:
        return await self._service.rate_album(self._user(ctx), args.album_id, args.rating)


class GetDashboardTool(_UserTool):
    name = "get_dashboard"
    description = "Listening statistics of the user: completed albums, tracks played, average rating, top genres and artists."

    async def execute(self, args: BaseModel, ctx: ToolContext) -> dict:
        return await self._service.get_dashboard(self._user(ctx))


def vinyl_tools(service: VinylShelfService) -> list[Tool]:
    return [SearchCatalogTool(service), GetCollectionTool(service), AddAlbumTool(service),
            UpdateProgressTool(service), CompleteAlbumTool(service), RateAlbumTool(service), GetDashboardTool(service)]
