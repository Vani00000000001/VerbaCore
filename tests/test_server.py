from fastapi.testclient import TestClient
from verbacore.server import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.2.0"


def test_models_endpoint():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "local" in data
    assert "cloud" in data
    assert "brain" in data
    assert "online" in data["brain"]


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "VerbaCore" in response.text


def test_reports_security_path_traversal():
    # Direct path traversal with dot-dot
    response = client.get("/api/reports/../../cloud_config.json")
    assert response.status_code in (400, 404)

    # Subdirectory traversal
    response = client.get("/api/reports/sub/file.pdf")
    assert response.status_code == 400

    # Nonexistent file returns 404
    response = client.get("/api/reports/nonexistent_report_12345.pdf")
    assert response.status_code == 404


def test_transcribe_missing_input():
    response = client.post("/api/transcribe")
    assert response.status_code == 400
