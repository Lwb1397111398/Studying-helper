"""跨端同步契约测试。"""

import re
from pathlib import Path

from app.modules.sync.schemas import (
    SYNC_COLLECTION_CONTRACT,
    SyncImportResult,
    SyncPackage,
    SyncPreviewResult,
)


REPO_ROOT = Path(__file__).resolve().parents[5]


def _read_repo_file(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _typescript_interface_body(source: str, interface_name: str) -> str:
    match = re.search(rf"export interface {interface_name} \{{(?P<body>.*?)\n\}}", source, re.S)
    assert match, f"找不到 TypeScript interface: {interface_name}"
    return match.group("body")


def _android_sync_package_body(source: str) -> str:
    match = re.search(r"data class SyncPackage\((?P<body>.*?)\n\)", source, re.S)
    assert match, "找不到 Android SyncPackage data class"
    return match.group("body")


def _snake_to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


def test_sync_collection_contract_matches_backend_models():
    for item in SYNC_COLLECTION_CONTRACT:
        assert item.package_field in SyncPackage.model_fields
        assert item.preview_count_field in SyncPreviewResult.model_fields
        assert item.import_count_field in SyncImportResult.model_fields


def test_sync_collection_contract_matches_frontend_types():
    source = _read_repo_file("frontend/src/api/sync.ts")
    preview_body = _typescript_interface_body(source, "SyncPreviewResult")
    import_body = _typescript_interface_body(source, "SyncImportResult")

    for item in SYNC_COLLECTION_CONTRACT:
        assert f"{item.preview_count_field}:" in preview_body
        assert f"{item.import_count_field}:" in import_body


def test_sync_collection_contract_matches_android_package_dto():
    source = _read_repo_file("android/app/src/main/java/com/studyinghelper/mobile/data/sync/SyncDtos.kt")
    package_body = _android_sync_package_body(source)

    for item in SYNC_COLLECTION_CONTRACT:
        if "_" in item.package_field:
            assert f'@SerialName("{item.package_field}")' in package_body
        else:
            assert re.search(rf"\bval {_snake_to_camel(item.package_field)}:", package_body)
