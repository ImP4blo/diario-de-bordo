"""Leva o seu histórico do modo local (SQLite) para a sua conta online (Supabase).

1. Descubra o id da sua conta: entre no app online e abra
   https://diario-de-bordo-api.onrender.com/api/me ... (ou veja em Supabase >
   Authentication > Users, coluna "UID").
2. Simule (não grava nada, só mostra o que faria):
       python -m uv run python scripts/transferir_historico.py --para SEU-ID
3. Se estiver tudo certo, grave de verdade:
       python -m uv run python scripts/transferir_historico.py --para SEU-ID --executar

O destino padrão é a linha SUPABASE_DATABASE_URL do seu .env. Rodar de novo não
duplica nada.
"""

import argparse
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))  # para importar o pacote "app" rodando da pasta scripts

from app.db import normalize_url, run_migrations  # noqa: E402
from app.services.transfer import transfer  # noqa: E402


def env_value(name: str) -> str | None:
    """Lê uma linha do .env sem mostrar o valor (ele pode conter a senha do banco)."""
    env = BASE_DIR / ".env"
    if not env.is_file():
        return None
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip() or None
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--para", required=True, help="id (UUID) da sua conta online")
    parser.add_argument("--de", default="local", help='usuário de origem (padrão: "local")')
    parser.add_argument("--origem", default=str(BASE_DIR / "data" / "diario.db"))
    parser.add_argument("--destino", help="URL do banco de destino (padrão: .env)")
    parser.add_argument("--executar", action="store_true", help="grava de verdade")
    args = parser.parse_args()

    try:
        uuid.UUID(args.para)
    except ValueError:
        sys.exit("--para precisa ser o id da conta (formato UUID).")

    destination = args.destino or env_value("SUPABASE_DATABASE_URL")
    if not destination:
        sys.exit("Sem destino: use --destino ou a linha SUPABASE_DATABASE_URL no .env.")
    if not Path(args.origem).is_file():
        sys.exit(f"Banco de origem não encontrado: {args.origem}")

    source = create_engine(f"sqlite:///{args.origem}")
    target = create_engine(normalize_url(destination), pool_pre_ping=True)
    run_migrations(target)  # garante que as tabelas existem e estão atualizadas

    report = transfer(source, target, args.de, args.para, execute=args.executar)

    mode = "GRAVADO" if args.executar else "SIMULAÇÃO (nada foi gravado)"
    print(f"\n=== {mode} ===")
    print(f"Falas: {report.entries_copied} copiadas, {report.entries_skipped} já existiam")
    print(f"Rotina: {'copiada' if report.routine_copied else 'não copiada'}")
    print(f"Diários: {report.diaries_copied} copiados, {report.diaries_skipped} já existiam")
    for note in report.notes:
        print(f"Obs.: {note}")
    if not args.executar:
        print("\nPara gravar de verdade, rode de novo com --executar.")


if __name__ == "__main__":
    main()
