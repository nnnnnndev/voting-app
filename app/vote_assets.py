"""Per-vote uploaded assets (ad-hoc candidate photos).

Stored under data/vote_assets/<vote_id>/. Served via the /vote-photos/ route
mounted in main.py. When a vote is closed, the creator can purge these
photos while keeping the names and results intact.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ASSETS_ROOT = Path("data") / "vote_assets"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def vote_dir(vote_id: str) -> Path:
    return ASSETS_ROOT / vote_id


def save_photo(vote_id: str, extra_id: str, upload_filename: str, data: bytes) -> str:
    """Save an uploaded photo for one ad-hoc candidate. Returns the stored
    filename (basename only)."""
    ext = Path(upload_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"unsupported image type: {ext}")
    if len(data) > MAX_BYTES:
        raise ValueError(f"image exceeds {MAX_BYTES // (1024 * 1024)} MB limit")
    folder = vote_dir(vote_id)
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = f"{extra_id}{ext}"
    (folder / safe_name).write_bytes(data)
    return safe_name


def purge_photos(vote_id: str) -> None:
    folder = vote_dir(vote_id)
    if folder.exists():
        shutil.rmtree(folder)
