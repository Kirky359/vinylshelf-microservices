import asyncio
import json

from vinyl_agents.agent.listener import AgentListener
from vinyl_agents.agent.service import FunctionCallingAgent
from vinyl_agents.exceptions import AgentError, GuardrailViolation, PromptInjectionDetected, TokenBudgetExceeded
from vinyl_agents.guardrails.token_budget import TokenBudget
from vinyl_agents.llm.schemas import TokenUsage
from vinyl_agents.tools.base import ToolContext


class ConsolePrinter(AgentListener):
    """Prints everything the agent does: usage, tool calls, results, blocked requests."""

    def on_blocked(self, error: GuardrailViolation) -> None:
        if isinstance(error, PromptInjectionDetected):
            print(f"\n⚠️  PROMPT INJECTION DETECTED!\n   Patterns: {error.patterns}")
        elif isinstance(error, TokenBudgetExceeded):
            print(f"\n⚠️  TOKEN LIMIT: {error.message}")
        else:
            print(f"\n⛔ Blocked ({error.code}): {error.message}")

    def on_usage(self, usage: TokenUsage, budget: TokenBudget) -> None:
        stats = budget.stats()
        print(f"\n📊 Token usage: prompt {usage.prompt_tokens}, completion {usage.completion_tokens}, "
              f"total {usage.total_tokens}\n   Session: {stats['total_tokens']} tokens, {stats['total_requests']} requests "
              f"(left: {stats['tokens_remaining']} tokens, {stats['requests_remaining']} requests)")

    def on_tool_call(self, round_no: int, name: str, args: dict) -> None:
        print(f"\n🔗 Round {round_no}: 🔧 {name}({json.dumps(args, ensure_ascii=False)})")

    def on_tool_result(self, name: str, result: dict) -> None:
        text = json.dumps(result, ensure_ascii=False)
        print(f"   ✅ {text[:300]}{'…' if len(text) > 300 else ''}")


class ConsoleController:
    """The 'controller' of Task 1: reads lines from the terminal and hands them to the agent."""

    def __init__(self, agent: FunctionCallingAgent, user_id: str):
        self._agent = agent
        self._ctx = ToolContext(user_id=user_id)

    async def run(self) -> None:
        print("VinylShelf function-calling agent. Commands: /stats, /exit")
        while True:
            try:
                line = (await asyncio.to_thread(input, "\n👤 You: ")).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line in ("/exit", "/quit"):
                break
            if line == "/stats":
                print(json.dumps(self._agent.budget.stats(), indent=2))
                continue
            if line:
                await self.handle(line)

    async def handle(self, line: str) -> None:
        try:
            reply = await self._agent.chat(line, self._ctx)
            print(f"\n🤖 Assistant: {reply.text}")
        except GuardrailViolation:
            pass  # already printed by the listener
        except AgentError as exc:
            print(f"\n❌ {exc.message}")
