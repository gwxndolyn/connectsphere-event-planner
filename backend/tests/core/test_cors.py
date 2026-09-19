from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_cors_preflight_allows_frontend_origin() -> None:
    response = client.options(
        "/api/events/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unknown_origin() -> None:
    response = client.get("/api/events/health", headers={"Origin": "http://evil.example.com"})

    assert "access-control-allow-origin" not in response.headers
