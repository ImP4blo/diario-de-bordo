def test_config_publica_nao_expoe_chaves(client):
    config = client.get("/api/config").json()
    assert config["timezone"] == "America/Sao_Paulo"
    assert "today" in config
    assert not any("key" in campo for campo in config)


def test_arquivos_js_sao_servidos_como_javascript(client):
    response = client.get("/js/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
