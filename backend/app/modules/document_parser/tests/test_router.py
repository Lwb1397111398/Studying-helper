"""文档解析路由测试"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.document_parser.router import get_parser_llm_client, start_parse


class ChunkedUploadFile:
    def __init__(self, filename: str, chunks: list[bytes]):
        self.filename = filename
        self._chunks = chunks
        self.read_sizes = []

    async def read(self, size: int = -1):
        self.read_sizes.append(size)
        if not self._chunks:
            return b""
        if size == -1:
            content = b"".join(self._chunks)
            self._chunks.clear()
            return content
        return self._chunks.pop(0)


@pytest.mark.asyncio
async def test_start_parse_writes_upload_in_chunks(tmp_path, monkeypatch):
    upload = ChunkedUploadFile("test.txt", [b"abc", b"def"])
    created_tasks = []

    monkeypatch.setattr(
        "app.modules.document_parser.router.settings",
        SimpleNamespace(FILE_STORAGE_DIR=str(tmp_path)),
    )

    def capture_task(coro):
        created_tasks.append(coro)
        coro.close()

    with patch("app.modules.document_parser.router.asyncio.create_task", side_effect=capture_task):
        resp = await start_parse(upload)

    assert "upload_id" in resp
    assert upload.read_sizes == [1024 * 1024, 1024 * 1024, 1024 * 1024]
    assert len(list(tmp_path.iterdir())) == 1
    assert next(tmp_path.iterdir()).read_bytes() == b"abcdef"
    assert len(created_tasks) == 1


@pytest.mark.asyncio
async def test_start_parse_passes_parser_llm_to_background_task(tmp_path, monkeypatch):
    upload = ChunkedUploadFile("test.txt", [b"abc"])
    parser_llm = object()
    scheduled = []

    monkeypatch.setattr(
        "app.modules.document_parser.router.settings",
        SimpleNamespace(FILE_STORAGE_DIR=str(tmp_path)),
    )

    def fake_execute_parse(**kwargs):
        return kwargs

    def capture_task(task):
        scheduled.append(task)

    monkeypatch.setattr("app.modules.document_parser.router._execute_parse", fake_execute_parse)
    with patch("app.modules.document_parser.router.asyncio.create_task", side_effect=capture_task):
        await start_parse(upload, parser_llm=parser_llm)

    assert len(scheduled) == 1
    assert scheduled[0]["parser_llm"] is parser_llm

