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


def test_cors_localhost_only():
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:7860",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:7860"

    blocked = client.options(
        "/api/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in blocked.headers


def test_cloud_config_does_not_echo_keys_and_handles_nulls():
    res = client.post("/api/cloud-config", json={"gemini_api_key": None, "auto_fallback": False})
    assert res.status_code == 200
    cfg = client.get("/api/cloud-config").json()
    assert "gemini_masked" not in cfg
    assert "groq_masked" not in cfg


def test_invalid_recording_id_returns_400_and_finalize_reads_expected_chunks():
    assert client.delete("/api/recordings/not-a-uuid").status_code == 400
    assert client.post("/api/transcribe", data={"recording_id": "not-a-uuid"}).status_code == 400

    start = client.post("/api/recordings/start", json={"name": "test.webm"}).json()
    rec_id = start["recording_id"]
    client.put(f"/api/recordings/{rec_id}/chunks/0", content=b"abc")
    bad_fin = client.post(f"/api/recordings/{rec_id}/finalize", json={"expected_chunks": 2})
    assert bad_fin.status_code == 400
    assert "1 of 2" in bad_fin.json()["detail"]
    client.delete(f"/api/recordings/{rec_id}")
