from datetime import date

from app.database.models import GenerationJob, JobStatus
from tests.conftest import make_payload


def test_completed_job_status(client, valid_payload):
    job_id = client.post("/api/jobs/", json=valid_payload).json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert body["status"] == "COMPLETED"
    assert body["total_recipients"] == 2
    assert body["successful_count"] == 2
    assert body["failed_count"] == 0
    assert body["completed_count"] == 2
    assert body["progress_percentage"] == 100
    assert body["completed_at"] is not None


def test_progress_while_job_is_still_processing(client, db_session):
    """Simulate a half-finished job: 65 ok + 2 failed out of 100 -> 67%."""
    job = GenerationJob(
        event_name="Demo",
        certificate_date=date(2026, 10, 8),
        total_recipients=100,
        successful_count=65,
        failed_count=2,
        status=JobStatus.PROCESSING.value,
    )
    db_session.add(job)
    db_session.commit()

    body = client.get(f"/api/jobs/{job.id}/").json()

    assert body["status"] == "PROCESSING"
    assert body["completed_count"] == 67
    assert body["progress_percentage"] == 67
    assert body["completed_at"] is None


def test_progress_never_shows_100_before_everything_is_done(client, db_session):
    job = GenerationJob(
        event_name="Demo",
        certificate_date=date(2026, 10, 8),
        total_recipients=3,
        successful_count=2,
        status=JobStatus.PROCESSING.value,
    )
    db_session.add(job)
    db_session.commit()

    assert client.get(f"/api/jobs/{job.id}/").json()["progress_percentage"] == 66


def test_status_of_bulk_job(client):
    job_id = client.post("/api/jobs/", json=make_payload(recipient_count=40)).json()["job_id"]
    body = client.get(f"/api/jobs/{job_id}/").json()
    assert body["successful_count"] == 40
    assert body["progress_percentage"] == 100


def test_unknown_job_returns_404(client):
    response = client.get("/api/jobs/does-not-exist/")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
