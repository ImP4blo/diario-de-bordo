"""Contrato comum a todos os provedores de IA.

O resto do app só conhece esta interface: "mande instruções + texto + formato
esperado e receba um JSON em texto". Trocar Groq por Claude (ou adicionar outro
provedor) não muda nenhuma linha fora da pasta app/llm/.
"""

from typing import Any, Protocol


class LLMError(Exception):
    """Falha ao falar com a IA (rede, cota, recusa, resposta vazia...)."""


class LLMNotConfiguredError(LLMError):
    """Falta a chave de API ou o provedor é desconhecido."""


class LLMProvider(Protocol):
    """Qualquer classe com estes atributos e este método serve como provedor.

    Protocol é a forma do Python dizer "tem que ter esse formato" sem obrigar
    herança (é o famoso duck typing: se faz quack, é pato).
    """

    name: str
    model: str

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        """Devolve o texto JSON da resposta, seguindo `schema` (JSON Schema)."""
        ...
