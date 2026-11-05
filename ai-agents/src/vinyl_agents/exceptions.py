class AgentError(Exception):
    """Base class of all errors of this project."""

    code = "agent_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ApiError(AgentError):
    """The VinylShelf REST API answered with a non-2xx status."""

    code = "api_error"

    def __init__(self, status_code: int, detail: str):
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class LlmError(AgentError):
    code = "llm_error"


class GuardrailViolation(AgentError):
    """A request was stopped by a guardrail."""

    code = "guardrail_violation"


class TokenBudgetExceeded(GuardrailViolation):
    code = "token_budget_exceeded"


class PromptInjectionDetected(GuardrailViolation):
    code = "prompt_injection_detected"

    def __init__(self, patterns: list[str]):
        super().__init__("Suspicious input blocked: " + ", ".join(patterns))
        self.patterns = patterns


class InvalidInput(GuardrailViolation):
    code = "invalid_input"


class UnknownTool(GuardrailViolation):
    code = "unknown_tool"


class InvalidToolArguments(GuardrailViolation):
    code = "invalid_tool_arguments"


class RateLimitExceeded(GuardrailViolation):
    code = "rate_limit_exceeded"


class ReadOnlyMode(GuardrailViolation):
    code = "read_only_mode"
