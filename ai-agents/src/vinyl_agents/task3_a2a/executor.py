from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part
from a2a.utils import new_agent_text_message

from vinyl_agents.agent.service import FunctionCallingAgent
from vinyl_agents.exceptions import AgentError, GuardrailViolation
from vinyl_agents.guardrails.rate_limiter import SlidingWindowRateLimiter
from vinyl_agents.llm.schemas import ToolCall
from vinyl_agents.task3_a2a.parser import A2ARequestParser, SkillRequest
from vinyl_agents.tools.base import ToolContext
from vinyl_agents.tools.registry import ToolRegistry


class SkillAgentExecutor(AgentExecutor):
    """Runs an A2A task: a structured request calls the skill directly, free text goes through the LLM agent
    (function calling with the same skills as tools). The result is returned as a JSON artifact."""

    def __init__(self, registry: ToolRegistry, text_agent: FunctionCallingAgent | None = None,
                 rate_limiter: SlidingWindowRateLimiter | None = None):
        self._registry = registry
        self._text_agent = text_agent
        self._limiter = rate_limiter or SlidingWindowRateLimiter(60)
        self._parser = A2ARequestParser()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.submit()
        await updater.start_work()
        try:
            self._limiter.acquire()
            data, summary = await self._run(self._parser.parse(context.message))
        except GuardrailViolation as exc:
            await updater.failed(new_agent_text_message(f"Rejected by guardrails ({exc.code}): {exc.message}",
                                                        context.context_id, context.task_id))
            return
        except AgentError as exc:
            await updater.failed(new_agent_text_message(exc.message, context.context_id, context.task_id))
            return
        if "error" in data:
            await updater.failed(new_agent_text_message(str(data["error"]), context.context_id, context.task_id))
            return
        await updater.add_artifact([Part(root=DataPart(data=data))], name="result")
        await updater.complete(new_agent_text_message(summary, context.context_id, context.task_id))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()

    async def _run(self, request: SkillRequest) -> tuple[dict, str]:
        if request.skill:
            result = await self._registry.invoke(ToolCall(name=request.skill, args=request.arguments), ToolContext())
            return result.result, f"skill {request.skill} executed"
        if not request.text:
            raise AgentError("send a DataPart {'skill': ..., 'arguments': ...} or a text request")
        if self._text_agent is None:
            raise AgentError("text requests need an LLM: set GEMINI_API_KEY or call a skill with a DataPart")
        reply = await self._text_agent.chat(request.text, ToolContext())
        return {"answer": reply.text, "skills_used": [i.model_dump() for i in reply.invocations]}, reply.text
