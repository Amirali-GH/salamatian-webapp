"""Media service — local filesystem storage with an S3-compatible interface.

Swap the `LocalStorage` class with an S3 implementation later without changing callers.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol

from fastapi import HTTPException, UploadFile

from app.config import settings

ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXCEL_MIME = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",  # some clients send this
}


class Storage(Protocol):
    async def save(self, data: BinaryIO, dest_rel: str) -> str: ...
    async def delete(self, rel_path: str) -> None: ...
    def url(self, rel_path: str) -> str: ...


class LocalStorage:
    def __init__(self, root: Path, public_prefix: str = "/media"):
        self.root = Path(root)
        self.public_prefix = public_prefix.rstrip("/")

    async def save(self, data: BinaryIO, dest_rel: str) -> str:
        target = self.root / dest_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(_copy_fileobj, data, target)
        return dest_rel

    async def delete(self, rel_path: str) -> None:
        target = self.root / rel_path
        if target.exists():
            await asyncio.to_thread(target.unlink)

    def url(self, rel_path: str) -> str:
        return f"{self.public_prefix}/{rel_path.lstrip('/')}"


def _copy_fileobj(src: BinaryIO, dest: Path) -> None:
    with open(dest, "wb") as out:
        shutil.copyfileobj(src, out)


# Default storage: one instance per logical bucket
cars_storage = LocalStorage(settings.cars_upload_dir, public_prefix="/media/cars")
leads_storage = LocalStorage(settings.leads_upload_dir, public_prefix="/media/leads")


def _ext_from_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime, ".bin")


async def validate_image_upload(upload: UploadFile) -> tuple[str, int]:
    """Return (mime, size_bytes) or raise HTTPException."""
    if upload.content_type not in ALLOWED_IMAGE_MIME:
        raise HTTPException(
            status_code=415, detail=f"Unsupported image type: {upload.content_type}"
        )
    max_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
    upload.file.seek(0, os.SEEK_END)
    size = upload.file.tell()
    upload.file.seek(0)
    if size > max_bytes:
        raise HTTPException(status_code=413, detail=f"Image too large (max {settings.MAX_IMAGE_SIZE_MB}MB)")
    return upload.content_type, size


async def save_car_image(upload: UploadFile, car_id: int) -> str:
    """Save a car image to storage. Returns the relative path (to /media/cars/)."""
    mime, _ = await validate_image_upload(upload)
    ext = _ext_from_mime(mime)
    rel_path = f"{car_id}/{uuid.uuid4().hex}{ext}"
    await cars_storage.save(upload.file, rel_path)
    return rel_path


async def save_lead_images(uploads: list[UploadFile]) -> list[str]:
    if len(uploads) > settings.MAX_LEAD_IMAGES:
        raise HTTPException(
            status_code=400, detail=f"Too many images (max {settings.MAX_LEAD_IMAGES})"
        )
    stored = []
    for upload in uploads:
        mime, _ = await validate_image_upload(upload)
        ext = _ext_from_mime(mime)
        rel_path = f"{uuid.uuid4().hex}{ext}"
        await leads_storage.save(upload.file, rel_path)
        stored.append(rel_path)
    return stored


def car_image_url(rel_path: str) -> str:
    return cars_storage.url(rel_path)


def lead_image_url(rel_path: str) -> str:
    return leads_storage.url(rel_path)


async def save_excel_upload(upload: UploadFile) -> Path:
    """Save uploaded Excel into STORAGE_ROOT/excel/. Returns absolute path."""
    if upload.content_type not in ALLOWED_EXCEL_MIME and not upload.filename.endswith(".xlsx"):
        raise HTTPException(status_code=415, detail="Expected .xlsx file")
    from datetime import datetime

    settings.excel_upload_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = Path(upload.filename or "upload.xlsx").name
    dest = settings.excel_upload_dir / f"{timestamp}_{safe_name}"
    await asyncio.to_thread(_copy_fileobj, upload.file, dest)
    return dest
