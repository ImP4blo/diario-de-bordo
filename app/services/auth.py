"""Quem está usando o app (login pelo Supabase Auth).

Depois do login, o Supabase entrega ao navegador um token JWT: um "crachá" assinado
digitalmente que diz quem é a pessoa e até quando vale. O navegador manda esse
crachá em toda requisição (cabeçalho Authorization) e aqui só conferimos:
1. a assinatura é do Supabase? (chave pública publicada por ele, a "JWKS")
2. ainda está na validade, é para este projeto (issuer) e para usuários logados (audience)?
Se estiver tudo certo, o campo "sub" do token é o id da pessoa.

Não guardamos senha nem sessão nenhuma: isso é trabalho do Supabase.
"""

from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

# Algoritmos de assinatura aceitos. Projetos novos do Supabase usam chaves
# assimétricas (ES256/RS256); projetos antigos usam um segredo compartilhado (HS256).
ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]
AUDIENCE = "authenticated"


@dataclass(frozen=True)
class CurrentUser:
    id: str
    name: str
    email: str | None = None


class AuthError(Exception):
    """Token ausente, inválido ou vencido."""


class TokenVerifier:
    def __init__(
        self, supabase_url: str, jwt_secret: str | None = None, jwk_client: Any = None
    ) -> None:
        self.issuer = f"{supabase_url.rstrip('/')}/auth/v1"
        self.jwt_secret = jwt_secret
        # O cliente baixa as chaves públicas uma vez e guarda em cache
        self.jwk_client = jwk_client or PyJWKClient(
            f"{self.issuer}/.well-known/jwks.json", cache_keys=True
        )

    def verify(self, token: str) -> CurrentUser:
        try:
            if jwt.get_unverified_header(token).get("alg") == "HS256":
                if not self.jwt_secret:
                    raise AuthError("Este projeto do Supabase usa SUPABASE_JWT_SECRET.")
                key: Any = self.jwt_secret
                algorithms = ["HS256"]
            else:
                key = self.jwk_client.get_signing_key_from_jwt(token).key
                algorithms = ASYMMETRIC_ALGORITHMS
            claims = jwt.decode(
                token, key, algorithms=algorithms, audience=AUDIENCE, issuer=self.issuer
            )
        except jwt.PyJWTError as err:
            raise AuthError("Sessão inválida ou expirada. Entre de novo.") from err
        return user_from_claims(claims)


def user_from_claims(claims: dict[str, Any]) -> CurrentUser:
    """Nome para o diário: o do Google, se houver; senão, o começo do e-mail."""
    email = claims.get("email") or None
    metadata = claims.get("user_metadata") or {}
    name = metadata.get("full_name") or metadata.get("name")
    if not name:
        name = email.split("@")[0] if email else "Usuário"
    return CurrentUser(id=claims["sub"], name=name, email=email)
