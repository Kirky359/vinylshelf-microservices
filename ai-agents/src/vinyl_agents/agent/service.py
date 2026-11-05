import itertools

from vinyl_agents.agent.listener import AgentListener
from vinyl_agents.config import Settings
from vinyl_agents.exceptions import GuardrailViolation, TokenBudgetExceeded
from vinyl_agents.guardrails.prompt_injection import InputValidator, PromptInjectionGuard
from vinyl_agents.guardrails.token_budget import TokenBudget
from vinyl_agents.llm.client import LlmClient
from vinyl_agents.llm.schemas import AgentReply, LlmResponse, Message, TokenUsage, ToolCall, ToolInvocation, ToolResult
from vinyl_agents.tools.base import ToolContext
from vinyl_agents.tools.registry import ToolRegistry


class FunctionCallingAgent:
    """The function-calling loop: LLM -> tool calls -> tool results -> LLM ... until it answers with text.

    Guardrails around it: input validation + injection scan (before), token budget (every round),
    argument validation + output sanitizing (inside the ToolRegistry).
    """

    def __init__(self, llm: LlmClient, registry: ToolRegistry, budget: TokenBudget, validator: InputValidator,
                 injection_guard: PromptInjectionGuard, system_prompt: str, settings: Settings,
                 listener: AgentListener | None = None):
        self._llm = llm
        self._registry = registry
        self._budget = budget
        self._validator = validator
        self._injection_guard = injection_guard
        self._system_prompt = system_prompt
        self._settings = settings
        self._listener = listener or AgentListener()
        self._history: list[Message] = []

    @property
    def budget(self) -> TokenBudget:
        return self._budget

    async def chat(self, user_message: str, ctx: ToolContext) -> AgentReply:
        text = self._accept(user_message)
        self._budget.begin_user_request()
        self._history.append(Message.user(text))
        invocations: list[ToolInvocation] = []
        usage = TokenUsage()
        try:
            for round_no in itertools.count(1):  # the limit is TokenBudget.check_before_call
                response = await self._ask_llm(round_no)
                usage += response.usage
                if not response.tool_calls:
                    self._history.append(Message(role="model", text=response.text,
                                                 provider_payload=response.provider_payload))
                    return AgentReply(text=response.text, invocations=invocations, usage=usage)
                self._history.append(Message(role="model", text=response.text, tool_calls=response.tool_calls,
                                             provider_payload=response.provider_payload))
                results = await self._run_tools(round_no, response.tool_calls, ctx, invocations)
                self._history.append(Message(role="tool", tool_results=results))
        except TokenBudgetExceeded as exc:
            self._listener.on_blocked(exc)
            raise

    def _accept(self, user_message: str) -> str:
        """Input guardrails: validation and prompt injection scan, before anything reaches the model."""
        try:
            text = self._validator.validate(user_message)
            self._injection_guard.check(text)
        except GuardrailViolation as exc:
            self._listener.on_blocked(exc)
            raise
        return text

    async def _ask_llm(self, round_no: int) -> LlmResponse:
        self._budget.check_before_call(round_no)
        response = await self._llm.generate(self._system_prompt, self._window(), self._registry.specs(),
                                            self._settings.max_output_tokens)
        self._budget.record(response.usage, response.model)
        self._listener.on_usage(response.usage, self._budget)
        return response

    async def _run_tools(self, round_no: int, calls: list[ToolCall], ctx: ToolContext,
                         invocations: list[ToolInvocation]) -> list[ToolResult]:
        results = []
        for call in calls[: self._settings.max_tool_calls_per_round]:
            self._listener.on_tool_call(round_no, call.name, call.args)
            result = await self._registry.invoke(call, ctx)
            self._listener.on_tool_result(call.name, result.result)
            invocations.append(ToolInvocation(name=call.name, args=call.args, result=result.result))
            results.append(result)
        return results

    def _window(self) -> list[Message]:
        """Last N messages, starting at a user message so tool results are never separated from their call."""
        window = self._history[-self._settings.max_history_messages:]
        while window and window[0].role != "user":
            window = window[1:]
        return window
