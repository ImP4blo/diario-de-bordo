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


def test_origens_do_cors_juntam_lista_e_dominio_do_render():
    from app.config import Settings

    settings = Settings(
        _env_file=None,
        allowed_origins="http://localhost:8000/, https://exemplo.com",
        frontend_host="diario-de-bordo.onrender.com",
    )
    assert settings.cors_origins == [
        "http://localhost:8000",
        "https://exemplo.com",
        "https://diario-de-bordo.onrender.com",
    ]


def test_sem_configuracao_nenhum_site_externo_e_liberado():
    from app.config import Settings

    assert Settings(_env_file=None).cors_origins == []
