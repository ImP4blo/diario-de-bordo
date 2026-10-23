"""Provedor Anthropic (Claude).

Usa "structured outputs": a API garante que a resposta é um JSON que segue o
schema enviado em output_config.format.
"""

from typing import Any

import anthropic

from app.llm.base import LLMError

DEFAULT_MODEL = "claude-opus-5-5"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "") -> None:
        self.model = model or DEFAULT_MODEL
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    # Organizar uma transcrição não exige raciocínio profundo
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": schema},
                },
                # Se o modelo recusar o pedido por segurança, a própria API tenta de
                # novo num modelo alternativo adequado, dentro da mesma chamada
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as err:
            raise LLMError("Chave da Anthropic inválida (ANTHROPIC_API_KEY).") from err
        except anthropic.RateLimitError as err:
            raise LLMError("Limite de uso da Anthropic atingido. Tente mais tarde.") from err
        except anthropic.APIStatusError as err:
            raise LLMError(f"Erro da Anthropic ({err.status_code}): {err.message}") from err
        except anthropic.APIConnectionError as err:
            raise LLMError("Sem conexão com a Anthropic.") from err

        if response.stop_reason == "refusal":
            raise LLMError("O modelo recusou o pedido.")
        if response.stop_reason == "max_tokens":
            raise LLMError("A resposta ficou grande demais e foi cortada.")

        text = next((b.text for b in response.content if b.type == "text"), "")
        if not text:
            raise LLMError("A Anthropic devolveu uma resposta vazia.")
        return text
