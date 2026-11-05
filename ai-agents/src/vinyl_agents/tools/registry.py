from pydantic import ValidationError

from vinyl_agents.exceptions import AgentError, ApiError, InvalidToolArguments, ReadOnlyMode, UnknownTool
from vinyl_agents.guardrails.output_sanitizer import ToolOutputSanitizer
from vinyl_agents.llm.schemas import ToolCall, ToolResult, ToolSpec
from vinyl_agents.tools.base import Tool, ToolContext


class ToolRegistry:
    """Allowlist of tools + the single place where a model-produced call is validated and executed (Level 3)."""

    def __init__(self, tools: list[Tool], sanitizer: ToolOutputSanitizer | None = None, read_only: bool = False):
        self._tools = {t.name: t for t in tools}
        self._sanitizer = sanitizer
        self._read_only = read_only

    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self._tools.values() if not (self._read_only and t.mutating)]

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise UnknownTool(f"tool '{name}' is not allowed")
        return self._tools[name]

    async def invoke(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        """Never raises for problems the model can fix itself: they are returned as {"error": ...} so it can recover."""
        try:
            tool = self.get(call.name)
            if self._read_only and tool.mutating:
                raise ReadOnlyMode(f"'{call.name}' changes data and the agent is in read-only mode")
            try:
                args = tool.args_model.model_validate(call.args)
            except ValidationError as exc:
                problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
                raise InvalidToolArguments(f"invalid arguments for {call.name}: {problems}") from exc
            result = await tool.execute(args, ctx)
        except ApiError as exc:
            result = {"error": exc.message, "http_status": exc.status_code}
        except AgentError as exc:
            result = {"error": exc.message, "error_code": exc.code}
        return ToolResult(name=call.name, result=self._sanitizer.sanitize(call.name, result) if self._sanitizer else result)
