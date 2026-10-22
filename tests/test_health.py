from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_retorna_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_e_servido_na_raiz():
    response = client.get("/")
    assert response.status_code == 200
    assert "Diário de Bordo" in response.text
