import pytest

from app.database.models import GenerationJob
from app.utils.validators import clean_text, is_path_inside, make_safe_filename_part
from tests.conftest import make_payload


def post_with(client, **changes):
    payload = make_payload()
    payload.update(changes)
    return client.post("/api/jobs/", json=payload)


@pytest.mark.parametrize(
    "changes, expected_field",
    [
        ({"event_name": ""}, "event_name"),
        ({"event_name": "   "}, "event_name"),
        ({"certificate_date": "not-a-date"}, "certificate_date"),
        ({"certificate_date": "2026-02-30"}, "certificate_date"),
        ({"recipients": []}, "recipients"),
        ({"recipients": [{"name": "", "email": "a@example.com"}]}, "recipients.0.name"),
        ({"recipients": [{"name": "   ", "email": "a@example.com"}]}, "recipients.0.name"),
        ({"recipients": [{"name": "Ann", "email": "not-an-email"}]}, "recipients.0.email"),
        ({"recipients": [{"name": "Ann", "email": ""}]}, "recipients.0.email"),
        ({"recipients": [{"name": "Ann"}]}, "recipients.0.email"),
        ({"recipients": [{"email": "a@example.com"}]}, "recipients.0.name"),
    ],
)
def test_invalid_input_returns_422_with_clear_message(client, changes, expected_field):
    response = post_with(client, **changes)

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Invalid request data"
    assert expected_field in [error["field"] for error in body["errors"]]
    assert all(error["message"] for error in body["errors"])


def test_empty_recipient_list_message(client):
    response = post_with(client, recipients=[])
    assert "at least one recipient" in response.json()["errors"][0]["message"]


def test_missing_fields_are_rejected(client):
    response = client.post("/api/jobs/", json={})
    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["errors"]}
    assert {"event_name", "certificate_date", "recipients"} <= fields


def test_malformed_json_is_rejected(client):
    response = client.post(
        "/api/jobs/", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_invalid_request_creates_nothing_in_database(client, db_session):
    post_with(client, recipients=[{"name": "Ann", "email": "bad"}])
    assert db_session.query(GenerationJob).count() == 0


def test_one_bad_recipient_rejects_the_whole_request(client, db_session):
    recipients = [
        {"name": "Good", "email": "good@example.com"},
        {"name": "Bad", "email": "bad-email"},
    ]
    response = post_with(client, recipients=recipients)
    assert response.status_code == 422
    assert db_session.query(GenerationJob).count() == 0


def test_too_many_recipients_is_rejected(client, monkeypatch):
    monkeypatch.setattr("app.schemas.job.MAX_RECIPIENTS_PER_JOB", 3)
    response = client.post("/api/jobs/", json=make_payload(recipient_count=4))
    assert response.status_code == 422
    assert "at most 3" in response.json()["errors"][0]["message"]


def test_whitespace_in_names_is_cleaned(client, db_session):
    recipients = [{"name": "  Sona    Mithya \n", "email": "sona@example.com"}]
    job_id = post_with(client, recipients=recipients).json()["job_id"]
    job = db_session.get(GenerationJob, job_id)
    assert job.certificates[0].name == "Sona Mithya"


# ---- helper functions -------------------------------------------------------

def test_clean_text():
    assert clean_text("  a \n  b\t c ") == "a b c"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Sona Mithya", "sona_mithya"),
        ("../../etc/passwd", "etc_passwd"),
        ("José Müller", "jose_muller"),
        ("..\\..\\windows", "windows"),
        ("!!!", "recipient"),
        ("சோனா", "recipient"),
    ],
)
def test_make_safe_filename_part(raw, expected):
    assert make_safe_filename_part(raw) == expected


def test_is_path_inside(tmp_path):
    assert is_path_inside(tmp_path / "a" / "b.pdf", tmp_path)
    assert not is_path_inside(tmp_path / ".." / "outside.pdf", tmp_path)
