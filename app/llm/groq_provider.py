"""Provedor Groq (plano gratuito, modelos abertos como o Llama).

O Groq garante que a resposta é um JSON válido (json_object), mas não força um
schema específico. Por isso o schema vai descrito nas instruções, e a validação
de verdade acontece depois, com Pydantic.
"""

import json
from typing import Any

import groq

from app.llm.base import LLMError

# Os modelos disponíveis mudam com o tempo: confira em https://console.groq.com/docs/models
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, model: str = "") -> None:
        self.model = model or DEFAULT_MODEL
        self.client = groq.Groq(api_key=api_key)

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        system_with_schema = (
            f"{system}\n\nResponda APENAS com um objeto JSON que siga exatamente este "
            f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}"
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_with_schema},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # baixo = respostas mais consistentes e menos "criativas"
            )
        except groq.AuthenticationError as err:
            raise LLMError("Chave do Groq inválida (GROQ_API_KEY).") from err
        except groq.RateLimitError as err:
            raise LLMError(
                "Limite do plano gratuito do Groq atingido. Espere um minuto e tente de novo."
            ) from err
        except groq.APIStatusError as err:
            raise LLMError(f"Erro do Groq ({err.status_code}): {err.message}") from err
        except groq.APIConnectionError as err:
            raise LLMError("Sem conexão com o Groq.") from err

        text = response.choices[0].message.content
        if not text:
            raise LLMError("O Groq devolveu uma resposta vazia.")
        return text
