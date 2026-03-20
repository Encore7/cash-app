from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_ingest_endpoint() -> None:
    response = client.post(
        '/runs/ingest',
        json={'tenant_code': 'bike-team-gmbh', 'business_date': '2026-03-19'},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['tenant_code'] == 'bike-team-gmbh'
    assert payload['status'] in {'REVIEW_REQUIRED', 'READY_TO_POST', 'POSTED'}
