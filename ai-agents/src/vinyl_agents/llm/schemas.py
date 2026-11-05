from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["user", "model", "tool"]


class ToolSpec(BaseModel):
    """What the LLM sees about a tool: name, description and the JSON schema of its arguments."""

    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    name: str
    result: dict[str, Any]


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(prompt_tokens=self.prompt_tokens + other.prompt_tokens,
                          completion_tokens=self.completion_tokens + other.completion_tokens,
                          total_tokens=self.total_tokens + other.total_tokens)


class Message(BaseModel):
    role: Role
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    provider_payload: Any = Field(default=None, exclude=True)  # provider-native content (e.g. Gemini thought signatures)

    @classmethod
    def user(cls, text: str) -> "Message":
        return cls(role="user", text=text)


class LlmResponse(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    model: str = ""
    provider_payload: Any = Field(default=None, exclude=True)


class ToolInvocation(BaseModel):
    """One executed tool call, kept for the trace shown to the user."""

    name: str
    args: dict[str, Any]
    result: dict[str, Any]


class AgentReply(BaseModel):
    text: str
    invocations: list[ToolInvocation] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
