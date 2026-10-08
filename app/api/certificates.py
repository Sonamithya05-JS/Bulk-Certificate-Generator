"""Endpoint for downloading one generated certificate."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_certificates_dir
from app.database.database import get_db
from app.database.models import Certificate, CertificateStatus
from app.utils.validators import is_path_inside

router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


@router.get("/{certificate_id}/", response_class=FileResponse)
def download_certificate(
    certificate_id: int,
    db: Session = Depends(get_db),
    certificates_dir: Path = Depends(get_certificates_dir),
) -> FileResponse:
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail=f"Certificate {certificate_id} not found")

    if certificate.status == CertificateStatus.FAILED.value:
        raise HTTPException(
            status_code=409,
            detail=f"Certificate generation failed: {certificate.error_message}",
        )
    if certificate.status != CertificateStatus.SUCCESS.value or not certificate.certificate_path:
        raise HTTPException(status_code=409, detail="Certificate is not ready yet")

    pdf_path = (certificates_dir / certificate.certificate_path).resolve()
    # Safety check: never serve a file outside the certificates directory.
    if not is_path_inside(pdf_path, certificates_dir) or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Certificate file not found on the server")

    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)
