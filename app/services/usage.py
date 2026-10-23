"""Limite diário de uso da IA do app (a cota paga por você).

Regras:
- Só vale no modo public. No seu PC (modo local), não há limite.
- 1 refinamento = 1 dia de diário gerado com sucesso. Falhou? Não conta.
- Dois limites: por pessoa e no total do app (protege a cota contra abuso).
- Quem usa a própria chave de IA não entra na conta.
"""

from dataclasses import dataclass
from datetime import date

from sqlmodel import Session

from app.config import Settings
from app.models import UsageCounter
from app.services.days import today

TOTAL = "total"


@dataclass(frozen=True)
class Usage:
    limit: int
    used: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


class QuotaExceededError(Exception):
    def __init__(self, message: str, remaining: int) -> None:
        super().__init__(message)
        self.remaining = remaining


class UsageLimiter:
    def __init__(self, session: Session, settings: Settings, day: date | None = None) -> None:
        self.session = session
        self.settings = settings
        self.day = day or today()
        self.enabled = settings.app_mode == "public"

    def _count(self, subject: str) -> int:
        counter = self.session.get(UsageCounter, (subject, self.day))
        return counter.count if counter else 0

    def usage(self, user_id: str) -> Usage:
        return Usage(self.settings.daily_refinements_per_user, self._count(f"user:{user_id}"))

    def check(self, user_id: str, needed: int) -> None:
        """Confere ANTES de chamar a IA se há saldo para `needed` dias."""
        if not self.enabled:
            return
        personal = self.usage(user_id)
        if personal.remaining < needed:
            if personal.remaining == 0:
                message = "Você usou seus refinamentos de hoje."
            else:
                message = (
                    f"Você tem {personal.remaining} refinamento(s) hoje e este período "
                    f"precisa de {needed}. Gere dia a dia ou use sua própria chave."
                )
            raise QuotaExceededError(message, personal.remaining)

        total_left = self.settings.daily_refinements_total - self._count(TOTAL)
        if total_left < needed:
            raise QuotaExceededError(
                "O limite diário do app foi atingido. Use sua própria chave ou tente amanhã.",
                personal.remaining,
            )

    def consume(self, user_id: str) -> None:
        """Registra 1 refinamento feito com sucesso."""
        if not self.enabled:
            return
        for subject in (f"user:{user_id}", TOTAL):
            counter = self.session.get(UsageCounter, (subject, self.day)) or UsageCounter(
                subject=subject, day=self.day
            )
            counter.count += 1
            self.session.add(counter)
        self.session.commit()
