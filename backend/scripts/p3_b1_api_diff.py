"""P3a-B1 API 级对比脚本：update_unit_graph 端点删除 existing_edges 死查询前后的响应 diff。

用法：python scripts/p3_b1_api_diff.py <输出json路径>
流程：内存 SQLite + TestClient → build 固定 fixture → update unit-1（命中删除的死查询路径）
→ GET 全图 → 三个响应按 key 排序规范化后落盘。前后两次输出完全一致 = 死查询删除无行为影响。
"""

import asyncio  # noqa: E402
import re  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession  # noqa: E402

from app.db.database import Base, get_db  # noqa: E402
from app.modules.knowledge_graph.router import router  # noqa: E402

UNITS = [
    {"id": "unit-1", "book_id": "book-1", "chapter_id": "chapter-1", "title": "数组基础",
     "content": "数组是一种线性表。", "summary": "数组是基本数据结构。",
     "concepts": ["数组", "线性表"], "difficulty_level": 2, "importance_score": 0.8},
    {"id": "unit-2", "book_id": "book-1", "chapter_id": "chapter-1", "title": "链表结构",
     "content": "链表通过指针连接。", "summary": "链表动态大小。",
     "concepts": ["链表", "线性表"], "difficulty_level": 3, "importance_score": 0.7,
     "prerequisites": ["数组基础"]},
]
CHAPTERS = [{"id": "chapter-1", "book_id": "book-1", "title": "第一章", "order": 1}]
BUILD_PAYLOAD = {"units": UNITS, "chapters": CHAPTERS, "mastery_records": []}
UPDATE_PAYLOAD = {"unit_id": "unit-1", "title": "数组基础(更新)", "concepts": ["数组", "线性表", "下标"],
                  "prerequisites": [], "summary": "更新后的数组", "key_points": ["下标从0开始"],
                  "difficulty_level": 2, "importance_score": 0.85}


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _stabilize(body: dict) -> dict:
    """把随机生成的 concept 节点 uuid id 替换为 label 基确定性 id，边引用同步映射。"""
    id_map = {}
    for node in body.get("nodes", []):
        if _UUID_RE.match(str(node.get("id", ""))):
            id_map[node["id"]] = f"auto:{node.get('label', '?')}"
    if not id_map:
        return body
    for node in body.get("nodes", []):
        node["id"] = id_map.get(node["id"], node["id"])
    for edge in body.get("edges", []):
        edge["source_id"] = id_map.get(edge["source_id"], edge["source_id"])
        edge["target_id"] = id_map.get(edge["target_id"], edge["target_id"])
        if _UUID_RE.match(str(edge.get("id", ""))):
            edge["id"] = f"auto-edge:{edge['source_id']}->{edge['target_id']}:{edge.get('relation_type')}"
    return body


def _normalize(obj):
    if isinstance(obj, dict):
        return {k: _normalize(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return sorted((_normalize(x) for x in obj), key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True))
    return obj


async def _capture() -> dict:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with maker() as session:
        app = FastAPI()
        app.include_router(router)

        async def override():
            yield session

        app.dependency_overrides[get_db] = override
        client = TestClient(app)
        r_build = client.post("/api/v1/knowledge-graph/book-1/build", json=BUILD_PAYLOAD)
        r_update = client.post("/api/v1/knowledge-graph/book-1/units/unit-1", json=UPDATE_PAYLOAD)
        r_get = client.get("/api/v1/knowledge-graph/book-1")
    await engine.dispose()
    return {"build": {"status": r_build.status_code, "body": r_build.json()},
            "update": {"status": r_update.status_code, "body": r_update.json()},
            "get": {"status": r_get.status_code, "body": r_get.json()}}


def main():
    out = Path(sys.argv[1])
    raw = asyncio.run(_capture())
    raw = {k: _stabilize(v["body"]) | {"status": v["status"]} for k, v in raw.items()}
    result = _normalize(raw)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"captured -> {out} (update={result['update']['status']}, get={result['get']['status']}, "
          f"nodes={len(result['get'].get('nodes', []))}, edges={len(result['get'].get('edges', []))})")


if __name__ == "__main__":
    main()
