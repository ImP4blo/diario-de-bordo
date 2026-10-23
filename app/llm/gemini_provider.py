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

# Apelidos que sempre apontam para o modelo mais recente: sobrevivem às descontinuações
DEFAULT_MODEL = "gemini-flash-latest"
# Plano B quando o principal está sobrecarregado: o Lite costuma estar mais livre
FALLBACK_MODEL = "gemini-flash-lite-latest"

# Erros passageiros do lado do Google (sobrecarga, instabilidade)
TRANSIENT_CODES = (500, 502, 503, 504)

# A própria biblioteca tenta de novo nesses erros: espera 2s, depois 4s...
RETRY = types.HttpRetryOptions(
    attempts=3, initial_delay=2, max_delay=10, http_status_codes=list(TRANSIENT_CODES)
)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "") -> None:
        self.model = model or DEFAULT_MODEL
        self._api_key = api_key
        self.client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(retry_options=RETRY)
        )

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        # Com o modelo padrão, se ele seguir sobrecarregado mesmo após as novas
        # tentativas, usamos o plano B. Modelo escolhido no .env não é trocado.
        models = [self.model, FALLBACK_MODEL] if self.model == DEFAULT_MODEL else [self.model]
        for index, model in enumerate(models):
            try:
                return self._call(model, system, prompt, schema)
            except errors.APIError as err:
                is_last = index == len(models) - 1
                if err.code in TRANSIENT_CODES and not is_last:
                    continue
                raise LLMError(self._friendly(err)) from None
        raise LLMError("O Gemini não respondeu.")  # nunca chega aqui; deixa o tipo claro

    def _call(self, model: str, system: str, prompt: str, schema: dict[str, Any]) -> str:
        try:
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_json_schema=schema,  # o Gemini segue o formato pedido
                    temperature=0.2,
                ),
            )
        except errors.APIError:
            raise  # tratado em generate_json (plano B ou mensagem amigável)
        # "from None" corta o erro original: ele poderia carregar a chave para logs
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
        if err.code in TRANSIENT_CODES:
            return (
                "O Gemini está sobrecarregado agora (instabilidade do Google). "
                "Tente de novo em alguns minutos."
            )
        return f"Erro do Gemini ({err.code}): {self._redact(str(err.message))}"

    def _redact(self, text: str) -> str:
        """Garantia extra: se a chave aparecer em alguma mensagem, ela é apagada."""
        return text.replace(self._api_key, "[chave oculta]")
