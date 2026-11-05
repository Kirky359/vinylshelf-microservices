from typing import Any

from a2a.types import DataPart, Message, TextPart
from pydantic import BaseModel


class SkillRequest(BaseModel):
    """What an incoming A2A message asks for: a concrete skill with arguments, or free text."""

    skill: str | None = None
    arguments: dict[str, Any] = {}
    text: str = ""


class A2ARequestParser:
    """DataPart {"skill": ..., "arguments": {...}} = direct skill call; TextPart = natural language for the LLM."""

    def parse(self, message: Message | None) -> SkillRequest:
        request = SkillRequest()
        for part in (message.parts if message else []):
            content = part.root
            if isinstance(content, DataPart) and "skill" in content.data:
                request.skill = str(content.data["skill"])
                request.arguments = dict(content.data.get("arguments") or {})
            elif isinstance(content, TextPart):
                request.text = (request.text + " " + content.text).strip()
        return request
