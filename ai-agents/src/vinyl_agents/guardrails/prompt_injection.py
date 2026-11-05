import re
import unicodedata
from datetime import datetime

from vinyl_agents.config import Settings
from vinyl_agents.exceptions import InvalidInput, PromptInjectionDetected
from vinyl_agents.guardrails.json_log import JsonLogFile

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))

# (name, regex): English, Ukrainian and Russian variants of the common attacks
INJECTION_PATTERNS: tuple[tuple[str, re.Pattern], ...] = tuple((name, re.compile(rx, re.I | re.M)) for name, rx in (
    ("instruction_override",
     r"(ignore|disregard|forget|override|bypass)\W+(\w+\W+){0,3}(instructions?|prompts?|rules?|guardrails?|restrictions?)"
     r"|(ігноруй|ігнорувати|проігноруй|забудь|обійди|игнорируй|забудь|обойди)\W+(\w+\W+){0,3}"
     r"(інструкці\w*|правил\w*|обмеження|обмеженн\w*|промпт\w*|инструкци\w*|ограничени\w*)"),
    ("prompt_extraction",
     r"(reveal|show|print|repeat|leak|display|покажи|виведи|повтори|выведи|покажи)\W+(\w+\W+){0,4}"
     r"(system\s+prompt|your\s+instructions|системн\w+\s+\w+|свої\s+інструкці\w*|свои\s+инструкци\w*)"),
    ("role_hijack",
     r"\byou\s+are\s+now\b|\bact\s+as\s+(an?\s+)?(admin|root|developer|system)\b|\bdeveloper\s+mode\b|\bjailbreak\b|\bDAN\b"
     r"|\bтепер\s+ти\b|\bти\s+тепер\b|\bтеперь\s+ты\b"),
    ("fake_role_marker", r"^\s*(system|assistant|developer)\s*:|<\|im_(start|end)\|>|\[/?INST\]|<<SYS>>|###\s*system"),
    ("markup_injection", r"<\s*/?\s*(script|iframe|object|embed|img)\b|javascript\s*:|\bon(error|load|click)\s*="),
    ("sql_injection",
     r"('|\")\s*;?\s*(drop|delete|insert|update|alter)\s+\w+|\bunion\s+(all\s+)?select\b|\bor\s+1\s*=\s*1\b|;\s*--"),
    ("path_traversal", r"\.\./|\.\.\\|%2e%2e"),
    ("other_user_access",
     r"\b(another|other|someone\s+else'?s?)\s+user'?s?\b|\bчужого\s+користувача|\bінш\w+\s+користувач\w*|\bчужого\s+пользователя"),
))


class InputValidator:
    """Cheap structural checks of the user message before any pattern matching."""

    def __init__(self, settings: Settings):
        self._max_chars = settings.max_user_message_chars

    def validate(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH).strip()  # defeat homoglyph / invisible tricks
        if not text:
            raise InvalidInput("empty message")
        if len(text) > self._max_chars:
            raise InvalidInput(f"message is too long ({len(text)} > {self._max_chars} characters)")
        if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in text):
            raise InvalidInput("control characters are not allowed")
        return text


class PromptInjectionGuard:
    """Level 3 guardrail: detects instruction override, prompt extraction, role hijack, markup/SQL/path injections."""

    def __init__(self, settings: Settings):
        self._log = JsonLogFile(settings.injection_log_path)
        self._attempts: list[dict] = self._log.read([])

    def scan(self, text: str) -> list[str]:
        normalized = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
        return [name for name, pattern in INJECTION_PATTERNS if pattern.search(normalized)]

    def check(self, text: str, source: str = "user") -> None:
        found = self.scan(text)
        if found:
            self.record_attempt(text, found, source)
            raise PromptInjectionDetected(found)

    def record_attempt(self, text: str, patterns: list[str], source: str) -> None:
        self._attempts.append({"timestamp": datetime.now().isoformat(), "source": source,
                               "patterns": patterns, "message": text[:200]})
        self._log.write(self._attempts)
