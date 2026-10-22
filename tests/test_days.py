from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.services.days import local_date_of, to_utc, week_bounds

SP = ZoneInfo("America/Sao_Paulo")


def test_fala_da_noite_fica_no_dia_local_e_nao_no_dia_utc():
    # 02:30 UTC do dia 27 = 23:30 do dia 26 em São Paulo
    instante = datetime(2026, 10, 27, 2, 30, tzinfo=UTC)
    assert local_date_of(instante, SP) == date(2026, 10, 26)


def test_horario_sem_fuso_e_tratado_como_local():
    sem_fuso = datetime(2026, 10, 26, 9, 0)
    assert to_utc(sem_fuso, SP) == datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def test_semana_vai_de_segunda_a_sexta():
    quarta = date(2026, 10, 28)
    assert week_bounds(quarta) == (date(2026, 10, 26), date(2026, 10, 30))


def test_domingo_pertence_a_semana_que_comecou_na_segunda_anterior():
    domingo = date(2026, 11, 1)
    assert week_bounds(domingo) == (date(2026, 10, 26), date(2026, 10, 30))
