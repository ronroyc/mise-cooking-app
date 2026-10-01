from sqlalchemy.exc import OperationalError

from app.database.db import get_db
from app.main import app


def test_health_reports_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_database_failure(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("database is gone"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"


def test_frontend_is_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Mise" in response.text


def test_unknown_api_route_returns_404(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
