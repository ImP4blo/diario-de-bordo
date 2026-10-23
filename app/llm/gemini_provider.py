"""Provedor Google Gemini, usado com a CHAVE DA PRÓPRIA PESSOA.

Quem passa do limite diário pode criar uma chave grátis no Google AI Studio e
continuar usando. A chave chega por requisição, é usada só naquela chamada e
nunca é salva nem escrita em log.

Atenção (aviso mostrado na tela): no plano gratuito, o Google pode usar o
conteúdo enviado para melhorar os produtos dele.
"""

from typing import Any

from google import genai
from google.genai import errors, types

from app.llm.base import LLMError

# Apelido que sempre aponta para o Flash mais recente: sobrevive às descontinuações
DEFAULT_MODEL = "gemini-flash-latest"


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "") -> None:
        self.model = model or DEFAULT_MODEL
        self._api_key = api_key
        self.client = genai.Client(api_key=api_key)

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_json_schema=schema,  # o Gemini segue o formato pedido
                    temperature=0.2,
                ),
            )
        # "from None" corta o erro original: ele poderia carregar a chave para logs
        except errors.APIError as err:
            raise LLMError(self._friendly(err)) from None
        except Exception:  # rede, DNS, timeout...
            raise LLMError("Sem conexão com o Gemini.") from None

        if not response.text:
            raise LLMError("O Gemini devolveu uma resposta vazia.")
        return response.text

    def _friendly(self, err: errors.APIError) -> str:
        if err.code in (400, 401, 403) and "key" in str(err.message).lower():
            return "Sua chave do Gemini é inválida. Confira se copiou a chave inteira."
        if err.code == 429:
            return "Sua chave do Gemini atingiu o limite gratuito. Tente mais tarde."
        return f"Erro do Gemini ({err.code}): {self._redact(str(err.message))}"

    def _redact(self, text: str) -> str:
        """Garantia extra: se a chave aparecer em alguma mensagem, ela é apagada."""
        return text.replace(self._api_key, "[chave oculta]")
