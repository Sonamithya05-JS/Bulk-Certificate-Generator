"""Small helpers for cleaning user text and keeping file paths safe."""
import re
import unicodedata
from pathlib import Path


def clean_text(value: str) -> str:
    """Trim the text and collapse repeated whitespace/newlines into single spaces."""
    return " ".join(value.split())


def make_safe_filename_part(value: str, max_length: int = 50, fallback: str = "recipient") -> str:
    """Turn any text into a safe filename fragment.

    "Sona Mithya"      -> "sona_mithya"
    "../../etc/passwd" -> "etc_passwd"   (no slashes or dots survive)
    "José Müller"      -> "jose_muller"
    """
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return slug[:max_length].strip("_") or fallback


def is_path_inside(path: Path, directory: Path) -> bool:
    """True only if `path` really lives inside `directory` (blocks path traversal)."""
    return path.resolve().is_relative_to(directory.resolve())
