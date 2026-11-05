from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from vinyl_agents.llm.schemas import ToolSpec


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StrictArgs(BaseModel):
    """Base of all tool argument models: unknown fields are rejected (the model cannot smuggle extra parameters)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ToolContext(BaseModel):
    """Trusted data of the current call. user_id comes from the session, never from the LLM."""

    user_id: str | None = None


class Tool(ABC):
    """A function the model may call (function calling) / an A2A skill. Subclass = one tool."""

    name: ClassVar[str]
    description: ClassVar[str]
    args_model: ClassVar[type[BaseModel]] = NoArgs
    mutating: ClassVar[bool] = False  # changes state -> blocked in read-only mode
    tags: ClassVar[tuple[str, ...]] = ()
    examples: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    async def execute(self, args: BaseModel, ctx: ToolContext) -> dict: ...

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, parameters=_clean_schema(self.args_model))


def _clean_schema(model: type[BaseModel]) -> dict:
    """JSON schema without the noise (titles) that LLM providers do not need."""

    def strip(node):
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node

    schema = strip(model.model_json_schema())
    schema.setdefault("properties", {})
    return schema
