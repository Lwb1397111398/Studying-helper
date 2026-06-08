"""数据同步API路由"""

import json

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ErrorCode, ServiceError
from app.db.database import get_db
from app.modules.sync.schemas import SyncImportResult, SyncPackage, SyncPreviewResult
from app.modules.sync.service import SyncService

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])

DEFAULT_USER_ID = "anonymous"


def _get_service(db: AsyncSession) -> SyncService:
    return SyncService(db)


@router.get("/export")
async def export_all_sync_package(
    db: AsyncSession = Depends(get_db),
):
    package = await _get_service(db).export_all(DEFAULT_USER_ID)
    content = package.model_dump(mode="json")
    return JSONResponse(
        content=content,
        headers={"Content-Disposition": 'attachment; filename="studying-helper-sync.json"'},
    )


@router.get("/books/{book_id}/export")
async def export_book_sync_package(
    book_id: str,
    db: AsyncSession = Depends(get_db),
):
    package = await _get_service(db).export_book(DEFAULT_USER_ID, book_id)
    content = package.model_dump(mode="json")
    filename = f"studying-helper-{book_id}-sync.json"
    return JSONResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/preview", response_model=SyncPreviewResult)
async def preview_sync_package(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    package = await _read_sync_package(file)
    return await _get_service(db).preview_package(package)


@router.post("/import", response_model=SyncImportResult)
async def import_sync_package(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    package = await _read_sync_package(file)
    return await _get_service(db).import_package(DEFAULT_USER_ID, package)


async def _read_sync_package(file: UploadFile) -> SyncPackage:
    try:
        raw = await file.read()
        data = json.loads(raw.decode("utf-8"))
        return SyncPackage.model_validate(data)
    except UnicodeDecodeError:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包必须是 UTF-8 JSON 文件")
    except json.JSONDecodeError:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包不是有效的 JSON 文件")
    except ValidationError as exc:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包结构无效", {"errors": exc.errors()})
