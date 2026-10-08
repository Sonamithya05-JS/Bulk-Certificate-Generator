"""Creates ONE PDF certificate. Knows nothing about jobs or the database."""
from datetime import date
from pathlib import Path

from reportlab.pdfgen import canvas

from app.utils.validators import make_safe_filename_part
from templates.certificate_template import PAGE_SIZE, draw_certificate

# ReportLab's built-in fonts use the "cp1252" (Western European) character set.
# Characters outside it (e.g. Tamil, Chinese, emoji) would print as garbage, so
# we reject them with a clear error instead of producing a broken certificate.
PDF_ENCODING = "cp1252"


class CertificateGenerationError(Exception):
    """Raised when a single certificate cannot be generated. The message is safe to show users."""


def _is_supported(character: str) -> bool:
    try:
        character.encode(PDF_ENCODING)
        return True
    except UnicodeEncodeError:
        return False


def _ensure_text_is_supported(label: str, text: str) -> None:
    unsupported = [char for char in dict.fromkeys(text) if not _is_supported(char)]
    if unsupported:
        raise CertificateGenerationError(
            f"{label} contains characters the certificate font cannot display: "
            f"{' '.join(unsupported)}"
        )


def _build_output_path(job_directory: Path, recipient_name: str) -> Path:
    """e.g. sona_mithya_certificate.pdf ; a second "Sona Mithya" gets sona_mithya_2_certificate.pdf."""
    base_name = make_safe_filename_part(recipient_name)
    candidate = job_directory / f"{base_name}_certificate.pdf"
    counter = 2
    while candidate.exists():
        candidate = job_directory / f"{base_name}_{counter}_certificate.pdf"
        counter += 1
    return candidate


def generate_certificate_pdf(
    recipient_name: str,
    event_name: str,
    certificate_date: date,
    job_directory: Path,
) -> Path:
    """Create the PDF inside `job_directory` and return its path."""
    display_name = recipient_name.upper()
    date_text = certificate_date.strftime("%d-%m-%Y")

    _ensure_text_is_supported("Recipient name", display_name)
    _ensure_text_is_supported("Event name", event_name)

    job_directory.mkdir(parents=True, exist_ok=True)
    output_path = _build_output_path(job_directory, recipient_name)

    try:
        pdf = canvas.Canvas(str(output_path), pagesize=PAGE_SIZE)
        pdf.setTitle(f"Certificate - {recipient_name}")
        draw_certificate(pdf, display_name, event_name, date_text)
        pdf.showPage()
        pdf.save()
    except ValueError as exc:  # text did not fit the template
        output_path.unlink(missing_ok=True)
        raise CertificateGenerationError(str(exc)) from exc
    except OSError as exc:  # disk full, permission problem, ...
        output_path.unlink(missing_ok=True)
        raise CertificateGenerationError("Could not write the PDF file to disk") from exc

    return output_path
