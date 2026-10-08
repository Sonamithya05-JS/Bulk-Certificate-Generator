from app.database.models import Certificate
from tests.conftest import make_payload


def create_job(client, payload):
    return client.post("/api/jobs/", json=payload).json()["job_id"]


def test_list_certificates_of_a_job(client, valid_payload):
    job_id = create_job(client, valid_payload)

    response = client.get(f"/api/jobs/{job_id}/certificates/")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert len(body["certificates"]) == 2
    first = body["certificates"][0]
    assert first["recipient_name"] == "Sona Mithya"
    assert first["email"] == "sona@example.com"
    assert first["status"] == "SUCCESS"
    assert first["download_url"] == f"/api/certificates/{first['certificate_id']}/"
    assert first["error_message"] is None


def test_download_certificate_returns_pdf(client, valid_payload):
    job_id = create_job(client, valid_payload)
    download_url = client.get(f"/api/jobs/{job_id}/certificates/").json()["certificates"][0][
        "download_url"
    ]

    response = client.get(download_url)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "sona_mithya_certificate.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_each_recipient_gets_a_different_pdf(client, valid_payload):
    job_id = create_job(client, valid_payload)
    items = client.get(f"/api/jobs/{job_id}/certificates/").json()["certificates"]
    first = client.get(items[0]["download_url"]).content
    second = client.get(items[1]["download_url"]).content
    assert first != second


def test_list_certificates_for_unknown_job_returns_404(client):
    assert client.get("/api/jobs/nope/certificates/").status_code == 404


def test_download_unknown_certificate_returns_404(client):
    response = client.get("/api/certificates/99999/")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_certificate_id_must_be_a_number(client):
    assert client.get("/api/certificates/abc/").status_code == 422


def test_download_failed_certificate_returns_409_with_reason(client):
    payload = make_payload(recipient_count=0)
    payload["recipients"] = [{"name": "சோனா", "email": "tamil@example.com"}]
    job_id = create_job(client, payload)
    item = client.get(f"/api/jobs/{job_id}/certificates/").json()["certificates"][0]

    response = client.get(f"/api/certificates/{item['certificate_id']}/")

    assert item["status"] == "FAILED"
    assert response.status_code == 409
    assert "cannot display" in response.json()["detail"]


def test_download_pending_certificate_returns_409(client, db_session, valid_payload):
    job_id = create_job(client, valid_payload)
    certificate = db_session.query(Certificate).filter_by(job_id=job_id).first()
    certificate.status = "PENDING"
    db_session.commit()

    assert client.get(f"/api/certificates/{certificate.id}/").status_code == 409


def test_missing_pdf_file_returns_404(client, certificates_dir, valid_payload):
    job_id = create_job(client, valid_payload)
    item = client.get(f"/api/jobs/{job_id}/certificates/").json()["certificates"][0]
    next((certificates_dir / job_id).glob("sona_mithya*.pdf")).unlink()

    response = client.get(item["download_url"])

    assert response.status_code == 404
    assert "file not found" in response.json()["detail"]


def test_path_traversal_in_database_is_not_served(client, db_session, tmp_path, valid_payload):
    """Even if a DB row is tampered with, files outside the certificates folder are never served."""
    (tmp_path / "secret.txt").write_text("top secret")
    job_id = create_job(client, valid_payload)
    certificate = db_session.query(Certificate).filter_by(job_id=job_id).first()
    certificate.certificate_path = "../secret.txt"
    db_session.commit()

    response = client.get(f"/api/certificates/{certificate.id}/")

    assert response.status_code == 404
    assert b"top secret" not in response.content
