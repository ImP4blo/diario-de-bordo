def registrar(client, ts, text="", **extra):
    client.post("/api/entries", json={"ts": ts, "text": text, **extra})


def exportar(client, query):
    response = client.get(f"/api/export/transcript?{query}")
    assert response.status_code == 200
    return response


def test_exporta_semana_agrupada_por_dia(client):
    registrar(client, "2026-10-26T10:00:00-03:00", "Diário, refinamento com o PO")
    registrar(client, "2026-10-26T10:05:00-03:00", "vamos ver o card")
    registrar(
        client, "2026-10-26T12:02:00-03:00", kind="pause", ends_at="2026-10-26T13:05:00-03:00"
    )
    registrar(client, "2026-10-27T09:00:00-03:00", "bom dia")

    texto = exportar(client, "start=2026-10-26&end=2026-10-30").text

    assert "Período: 26/10/2026 a 30/10/2026" in texto
    assert "## Segunda-feira, 26/10/2026" in texto
    assert "- 10:00 [ANOTAÇÃO] Refinamento com o PO" in texto
    assert "- 12:02–13:05 [Pausa]" in texto
    assert "## Terça-feira, 27/10/2026" in texto
    # A segunda vem antes da terça
    assert texto.index("Segunda-feira") < texto.index("Terça-feira")


def test_arquivo_vem_como_download_com_nome_do_periodo(client):
    response = exportar(client, "start=2026-10-26&end=2026-10-30")
    disposition = response.headers["content-disposition"]
    assert 'filename="transcricao_2026-10-26_a_2026-10-30.md"' in disposition


def test_exporta_um_dia_em_txt_sem_markdown(client):
    registrar(client, "2026-10-26T10:00:00-03:00", "olá")
    response = exportar(client, "start=2026-10-26&fmt=txt")

    assert "transcricao_2026-10-26.txt" in response.headers["content-disposition"]
    assert "== Segunda-feira, 26/10/2026 ==" in response.text
    assert "10:00 [Fala] olá" in response.text
    assert "#" not in response.text


def test_periodo_vazio_avisa(client):
    assert "Nenhum registro no período." in exportar(client, "start=2026-10-26").text


def test_data_final_antes_da_inicial_e_rejeitada(client):
    response = client.get("/api/export/transcript?start=2026-10-30&end=2026-10-26")
    assert response.status_code == 422
