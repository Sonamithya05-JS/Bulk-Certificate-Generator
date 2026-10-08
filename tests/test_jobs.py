from app.database.models import Certificate, GenerationJob
from tests.conftest import make_payload


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_job_returns_job_id(client, valid_payload):
    response = client.post("/api/jobs/", json=valid_payload)

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"]
    assert body["status"] == "PROCESSING"
    assert body["total_recipients"] == 2


def test_create_job_saves_job_and_recipients_in_database(client, db_session, valid_payload):
    job_id = client.post("/api/jobs/", json=valid_payload).json()["job_id"]

    job = db_session.get(GenerationJob, job_id)
    assert job.event_name == "Python Workshop"
    assert str(job.certificate_date) == "2026-10-08"
    assert job.total_recipients == 2
    assert [c.name for c in job.certificates] == ["Sona Mithya", "Priya"]


def test_each_job_gets_a_unique_id(client, valid_payload):
    first = client.post("/api/jobs/", json=valid_payload).json()["job_id"]
    second = client.post("/api/jobs/", json=valid_payload).json()["job_id"]
    assert first != second


def test_bulk_request_with_100_recipients_in_one_call(client, db_session):
    response = client.post("/api/jobs/", json=make_payload(recipient_count=100))

    assert response.status_code == 202
    assert response.json()["total_recipients"] == 100
    assert db_session.query(Certificate).count() == 100
