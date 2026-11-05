"""Skills of the Producer agent = the messages collection-service produces in lab 3 (through the transactional outbox)."""
from pydantic import BaseModel

from vinyl_agents.tools.base import StrictArgs, Tool, ToolContext
from vinyl_agents.vinylshelf.service import VinylShelfService
from vinyl_agents.vinylshelf.types import Identifier, TracksPlayed, UserId


class _AlbumArgs(StrictArgs):
    user_id: UserId
    album_id: Identifier


class _ProgressArgs(_AlbumArgs):
    tracks_played: TracksPlayed


class _CompletedArgs(_AlbumArgs):
    wait: bool = True


class _SagaArgs(StrictArgs):
    saga_id: Identifier


class _ProducerSkill(Tool):
    mutating = True
    tags = ("producer", "events", "outbox")

    def __init__(self, service: VinylShelfService):
        self._service = service


class PublishAlbumAddedSkill(_ProducerSkill):
    name = "publish_album_added"
    description = "Produce the event collection.album_added: adds the album to the user's collection; the event goes " \
                  "to RabbitMQ through the transactional outbox."
    args_model = _AlbumArgs
    examples = ("Add album a1 to the collection of user <id>",)

    async def execute(self, args: _AlbumArgs, ctx: ToolContext) -> dict:
        item = await self._service.add_album(args.user_id, args.album_id)
        return {"event_type": "collection.album_added", "user_id": args.user_id, "album_id": args.album_id,
                "album_status": item["status"]}


class PublishProgressUpdatedSkill(_ProducerSkill):
    name = "publish_progress_updated"
    description = "Produce the event collection.progress_updated: sets the number of played tracks of an album."
    args_model = _ProgressArgs
    examples = ("User <id> has played 3 tracks of album a1",)

    async def execute(self, args: _ProgressArgs, ctx: ToolContext) -> dict:
        item = await self._service.update_progress(args.user_id, args.album_id, args.tracks_played)
        return {"event_type": "collection.progress_updated", "user_id": args.user_id, "album_id": args.album_id,
                "tracks_played": item["tracks_played"], "album_status": item["status"]}


class PublishAlbumCompletedSkill(_ProducerSkill):
    name = "publish_album_completed"
    description = "Produce the event collection.album_completed: starts the completion SAGA. With wait=true returns " \
                  "its final state (processed = confirmed by the consumer, compensated = rolled back)."
    args_model = _CompletedArgs
    examples = ("Complete album a1 for user <id>",)

    async def execute(self, args: _CompletedArgs, ctx: ToolContext) -> dict:
        result = await self._service.complete_album(args.user_id, args.album_id, wait=args.wait)
        return {"event_type": "collection.album_completed", "user_id": args.user_id, **result}


class GetPublicationStatusSkill(Tool):
    name = "get_publication_status"
    description = "State of a SAGA started by publish_album_completed: started, sent, processed or compensated."
    args_model = _SagaArgs
    tags = ("producer", "saga")

    def __init__(self, service: VinylShelfService):
        self._service = service

    async def execute(self, args: BaseModel, ctx: ToolContext) -> dict:
        return await self._service.get_saga(args.saga_id)


def producer_skills(service: VinylShelfService) -> list[Tool]:
    return [PublishAlbumAddedSkill(service), PublishProgressUpdatedSkill(service),
            PublishAlbumCompletedSkill(service), GetPublicationStatusSkill(service)]
