from datetime import date

import pytest

from app.services.certificate_generator import (
    CertificateGenerationError,
    generate_certificate_pdf,
)
from tests.conftest import make_payload


def generate(tmp_path, name="Sona Mithya", event="Python Workshop"):
    return generate_certificate_pdf(name, event, date(2026, 10, 8), tmp_path / "job1")


def test_generates_a_real_pdf_file(tmp_path):
    pdf_path = generate(tmp_path)

    assert pdf_path.exists()
    assert pdf_path.name == "sona_mithya_certificate.pdf"
    content = pdf_path.read_bytes()
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_file_is_created_inside_the_given_directory(tmp_path):
    pdf_path = generate(tmp_path, name="../../evil")
    assert pdf_path.parent == tmp_path / "job1"
    assert pdf_path.name == "evil_certificate.pdf"


def test_duplicate_names_do_not_overwrite_each_other(tmp_path):
    first = generate(tmp_path)
    second = generate(tmp_path)
    assert first != second
    assert first.exists() and second.exists()
    assert second.name == "sona_mithya_2_certificate.pdf"


def test_accented_latin_names_are_supported(tmp_path):
    assert generate(tmp_path, name="José Müller O’Brien").exists()


def test_long_event_name_wraps_instead_of_failing(tmp_path):
    long_event = "Advanced Distributed Systems and Cloud-Native Architecture Bootcamp 2026"
    assert generate(tmp_path, event=long_event).exists()


def test_unsupported_characters_raise_clear_error_and_leave_no_file(tmp_path):
    with pytest.raises(CertificateGenerationError, match="cannot display"):
        generate(tmp_path, name="சோனா")
    assert list((tmp_path / "job1").glob("*.pdf")) == []


def test_name_too_long_for_the_page_raises_error(tmp_path):
    with pytest.raises(CertificateGenerationError, match="too long"):
        generate(tmp_path, name="W" * 80)
    assert not list((tmp_path / "job1").glob("*.pdf"))


def test_api_creates_one_pdf_per_recipient(client, certificates_dir, valid_payload):
    job_id = client.post("/api/jobs/", json=valid_payload).json()["job_id"]

    files = sorted(path.name for path in (certificates_dir / job_id).glob("*.pdf"))
    assert files == ["priya_certificate.pdf", "sona_mithya_certificate.pdf"]


def test_api_generates_all_certificates_for_a_bulk_job(client, certificates_dir):
    job_id = client.post("/api/jobs/", json=make_payload(recipient_count=25)).json()["job_id"]
    assert len(list((certificates_dir / job_id).glob("*.pdf"))) == 25
