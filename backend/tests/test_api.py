
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200


def test_database_connection_endpoint():
    response = client.get("/db-test")
    assert response.status_code == 200


def test_tickets_endpoint():
    response = client.get("/tickets")
    assert response.status_code == 200
    assert isinstance(response.json(), (list, dict))


def test_articles_endpoint():
    response = client.get("/articles")
    assert response.status_code == 200
    assert isinstance(response.json(), (list, dict))


def test_stats_endpoint():
    response = client.get("/stats")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_audit_endpoint():
    response = client.get("/audit")
    assert response.status_code == 200

    data = response.json()
    assert "finding_count" in data
    assert "findings_by_rule" in data
    assert "findings" in data
    assert data["finding_count"] >= 0


def test_ticket_not_found():
    response = client.get("/tickets/TKT-DOES-NOT-EXIST")
    assert response.status_code == 404
