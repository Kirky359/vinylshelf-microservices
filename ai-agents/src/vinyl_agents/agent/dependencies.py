from functools import cached_property

from vinyl_agents.agent.listener import AgentListener
from vinyl_agents.agent.service import FunctionCallingAgent
from vinyl_agents.config import Settings
from vinyl_agents.dependencies import CoreContainer
from vinyl_agents.guardrails.output_sanitizer import ToolOutputSanitizer
from vinyl_agents.guardrails.prompt_injection import InputValidator, PromptInjectionGuard
from vinyl_agents.guardrails.token_budget import TokenBudget
from vinyl_agents.llm.client import LlmClient
from vinyl_agents.llm.gemini import GeminiClient
from vinyl_agents.llm.prompts import PromptFactory
from vinyl_agents.tools.base import Tool
from vinyl_agents.tools.registry import ToolRegistry
from vinyl_agents.tools.vinyl_tools import vinyl_tools
from vinyl_agents.vinylshelf.client import VinylShelfClient


class AgentContainer(CoreContainer):
    """The core dependencies plus everything an LLM agent needs: model, guardrails, tools. Used by Task 1 and by the
    text interface of the A2A agents; the MCP server needs only the CoreContainer."""

    def __init__(self, settings: Settings | None = None, client: VinylShelfClient | None = None,
                 llm: LlmClient | None = None):
        super().__init__(settings, client)
        self._llm = llm

    @property
    def llm_available(self) -> bool:
        return self._llm is not None or bool(self.settings.gemini_api_key)

    @cached_property
    def llm(self) -> LlmClient:
        return self._llm or GeminiClient(self.settings)

    @cached_property
    def injection_guard(self) -> PromptInjectionGuard:
        return PromptInjectionGuard(self.settings)

    @cached_property
    def input_validator(self) -> InputValidator:
        return InputValidator(self.settings)

    @cached_property
    def sanitizer(self) -> ToolOutputSanitizer:
        return ToolOutputSanitizer(self.settings, self.injection_guard)

    def tool_registry(self, tools: list[Tool] | None = None, read_only: bool = False,
                      sanitize: bool = True) -> ToolRegistry:
        return ToolRegistry(tools if tools is not None else vinyl_tools(self.vinyl_service),
                            self.sanitizer if sanitize else None, read_only)

    def agent(self, registry: ToolRegistry | None = None, listener: AgentListener | None = None,
              system_prompt: str | None = None) -> FunctionCallingAgent:
        """A new agent = a new conversation with its own token budget."""
        return FunctionCallingAgent(
            llm=self.llm, registry=registry or self.tool_registry(), budget=TokenBudget(self.settings),
            validator=self.input_validator, injection_guard=self.injection_guard,
            system_prompt=system_prompt or PromptFactory.build(self.settings.prompt_style),
            settings=self.settings, listener=listener)
