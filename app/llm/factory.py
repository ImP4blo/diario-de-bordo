"""Escolhe o provedor de IA a partir do .env (LLM_PROVIDER, LLM_MODEL e chaves)."""

from app.config import Settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMNotConfiguredError, LLMProvider
from app.llm.groq_provider import GroqProvider


def create_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMNotConfiguredError("Configure ANTHROPIC_API_KEY no arquivo .env.")
        return AnthropicProvider(settings.anthropic_api_key.get_secret_value(), settings.llm_model)

    if not settings.groq_api_key:
        raise LLMNotConfiguredError(
            "Configure GROQ_API_KEY no arquivo .env (crie a chave em https://console.groq.com)."
        )
    return GroqProvider(settings.groq_api_key.get_secret_value(), settings.llm_model)
