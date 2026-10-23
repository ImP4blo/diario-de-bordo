def test_config_publica_nao_expoe_segredos(client):
    config = client.get("/api/config").json()
    assert config["timezone"] == "America/Sao_Paulo"
    assert "today" in config
    # A publishable key do Supabase é pública por natureza; segredo é chave de IA,
    # senha do banco ou o segredo de assinatura dos tokens
    proibidos = ("api_key", "secret", "password", "database")
    assert not any(p in campo for campo in config for p in proibidos)


def test_arquivos_js_sao_servidos_como_javascript(client):
    response = client.get("/js/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
