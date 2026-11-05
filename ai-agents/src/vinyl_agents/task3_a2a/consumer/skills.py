"""Skills of the Consumer agent = analytics-consumer of lab 3, plus the integration with the Producer agent over A2A."""
import asyncio
import time
from typing import Literal

from vinyl_agents.exceptions import AgentError
from vinyl_agents.task3_a2a.remote_client import RemoteAgentClient
from vinyl_agents.tools.base import StrictArgs, Tool, ToolContext
from vinyl_agents.vinylshelf.service import VinylShelfService
from vinyl_agents.vinylshelf.types import Identifier, TracksPlayed, UserId


class _UserArgs(StrictArgs):
    user_id: UserId


class _RequestEventArgs(_UserArgs):
    event: Literal["album_added", "progress_updated", "album_completed"]
    album_id: Identifier
    tracks_played: TracksPlayed | None = None


class GetUserDashboardSkill(Tool):
    name = "get_user_dashboard"
    description = "Statistics the consumer has built from the received events: completed albums, tracks played, " \
                  "average rating, top genres and artists."
    args_model = _UserArgs
    tags = ("consumer", "analytics")
    examples = ("Show the dashboard of user <id>",)

    def __init__(self, service: VinylShelfService):
        self._service = service

    async def execute(self, args: _UserArgs, ctx: ToolContext) -> dict:
        return await self._service.get_dashboard(args.user_id)


class ListReceivedEventsSkill(Tool):
    name = "list_received_events"
    description = "Events that reached the consumer (its transactional inbox): message id, event type, saga id, " \
                  "status (processed / failed) and number of deliveries."
    args_model = _UserArgs
    tags = ("consumer", "inbox")

    def __init__(self, service: VinylShelfService):
        self._service = service

    async def execute(self, args: _UserArgs, ctx: ToolContext) -> dict:
        return await self._service.get_inbox(args.user_id)


class RequestEventSkill(Tool):
    """Agent-to-agent integration: asks the Producer agent (A2A) to produce an event and checks that it arrived."""

    name = "request_event"
    description = "Ask the Producer agent over A2A to produce an event (album_added, progress_updated, album_completed) " \
                  "and verify that it was delivered to this consumer. Returns the producer's answer and the delivery status."
    args_model = _RequestEventArgs
    mutating = True
    tags = ("consumer", "a2a", "integration")
    examples = ("Ask the producer to complete album a1 for user <id> and confirm the delivery",)

    def __init__(self, service: VinylShelfService, producer: RemoteAgentClient, delivery_wait_seconds: float):
        self._service = service
        self._producer = producer
        self._wait = delivery_wait_seconds

    async def execute(self, args: _RequestEventArgs, ctx: ToolContext) -> dict:
        skill, arguments = self._skill_call(args)
        event_type = f"collection.{args.event}"
        before = await self._count(args.user_id, event_type)
        state, data, text = await self._producer.send({"skill": skill, "arguments": arguments})
        if state != "completed" or data is None:
            return {"error": f"producer agent answered '{state}': {text}"}
        delivery = await self._wait_for_delivery(args.user_id, event_type, before, data.get("saga_id"))
        return {"producer": {"skill": skill, "task_state": state, "result": data}, "delivery": delivery,
                "dashboard": await self._service.get_dashboard(args.user_id)}

    @staticmethod
    def _skill_call(args: _RequestEventArgs) -> tuple[str, dict]:
        base = {"user_id": args.user_id, "album_id": args.album_id}
        if args.event == "progress_updated":
            if args.tracks_played is None:
                raise AgentError("tracks_played is required for progress_updated")
            return "publish_progress_updated", {**base, "tracks_played": args.tracks_played}
        return {"album_added": "publish_album_added", "album_completed": "publish_album_completed"}[args.event], base

    async def _rows(self, user_id: str, event_type: str) -> list[dict]:
        return [r for r in (await self._service.get_inbox(user_id))["inbox"] if r["event"] == event_type]

    async def _count(self, user_id: str, event_type: str) -> int:
        return len(await self._rows(user_id, event_type))

    async def _wait_for_delivery(self, user_id: str, event_type: str, before: int, saga_id: str | None) -> dict:
        deadline = time.monotonic() + self._wait
        while True:
            rows = await self._rows(user_id, event_type)
            match = next((r for r in rows if saga_id and r["saga_id"] == saga_id), None)
            if match is None and not saga_id and len(rows) > before:
                match = rows[0]  # inbox is ordered newest first
            if match:
                return {"delivered": True, "inbox_status": match["status"], "message_id": match["message_id"],
                        "deliveries": match["deliveries"]}
            if time.monotonic() >= deadline:
                return {"delivered": False, "note": f"no inbox record after {self._wait:.0f} s"}
            await asyncio.sleep(0.5)


def consumer_skills(service: VinylShelfService, producer: RemoteAgentClient, delivery_wait_seconds: float) -> list[Tool]:
    return [GetUserDashboardSkill(service), ListReceivedEventsSkill(service),
            RequestEventSkill(service, producer, delivery_wait_seconds)]
