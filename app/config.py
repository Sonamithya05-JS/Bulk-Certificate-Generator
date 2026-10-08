"""Application settings.

Values come from environment variables (or a .env file) with safe defaults,
so the project runs without any configuration.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = the folder that contains the "app" package.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _resolve_path(value: str) -> Path:
    """Relative paths are treated as relative to the project root."""
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


DATABASE_URL: str = os.getenv(
    "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'bulk_certificates.db').as_posix()}"
)
CERTIFICATES_DIR: Path = _resolve_path(os.getenv("CERTIFICATES_DIR", "generated_certificates"))
MAX_RECIPIENTS_PER_JOB: int = int(os.getenv("MAX_RECIPIENTS_PER_JOB", "1000"))


def get_certificates_dir() -> Path:
    """FastAPI dependency. Tests override this to use a temporary folder."""
    return CERTIFICATES_DIR
