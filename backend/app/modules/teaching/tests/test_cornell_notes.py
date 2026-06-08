"""康奈尔笔记功能测试"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.common.llm_client import LLMResponse
from app.modules.teaching.schemas import Annotation, CornellNote
from app.modules.teaching.service import TeachingService


def _make_mock_db_session():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()
    return mock_db


class TestCornellSchemas:
    """测试康奈尔笔记数据模型"""

    def test_annotation_with_cornell_fields(self):
        """Annotation 支持康奈尔字段"""
        annotation = Annotation(
            id="a-1",
            user_id="user-1",
            knowledge_unit_id="unit-1",
            annotation_type="cornell_note",
            content="笔记内容",
            cornell_cues=["线索1", "线索2"],
            cornell_summary="这是总结",
        )
        assert annotation.annotation_type == "cornell_note"
        assert len(annotation.cornell_cues) == 2
        assert annotation.cornell_summary == "这是总结"

    def test_annotation_cornell_defaults(self):
        """Annotation 康奈尔字段默认值"""
        annotation = Annotation(
            id="a-1",
            user_id="user-1",
            knowledge_unit_id="unit-1",
            annotation_type="note",
            content="普通笔记",
        )
        assert annotation.cornell_cues == []
        assert annotation.cornell_summary is None

    def test_cornell_note_model(self):
        """CornellNote 响应模型"""
        note = CornellNote(
            annotation_id="a-1",
            knowledge_unit_id="unit-1",
            notes="笔记内容",
            cues=["线索1", "线索2"],
            summary="总结",
            ai_generated=True,
        )
        assert note.ai_generated is True
        assert len(note.cues) == 2


class TestCornellServiceMethods:
    """测试康奈尔笔记服务方法"""

    @pytest.mark.asyncio
    async def test_generate_cornell_cues(self, mock_llm):
        """AI 生成线索栏"""
        mock_llm.chat_json = AsyncMock(return_value={
            "cues": ["什么是数组？", "连续存储的优势", "随机访问的原理"]
        })

        mock_db = _make_mock_db_session()
        mock_unit = MagicMock()
        mock_unit.title = "数组基础"
        mock_unit.key_points = json.dumps(["连续存储", "随机访问"])

        # 第一次 execute 查 KnowledgeUnitModel，第二次查 AnnotationModel
        mock_unit_result = MagicMock()
        mock_unit_result.scalar_one_or_none = MagicMock(return_value=mock_unit)
        mock_ann_result = MagicMock()
        mock_ann_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(side_effect=[mock_unit_result, mock_ann_result])

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        result = await service.generate_cornell_cues("unit-1", "数组是连续存储的数据结构")
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_generate_cornell_summary(self, mock_llm):
        """AI 生成总结栏"""
        mock_llm.chat_json = AsyncMock(return_value={
            "summary": "数组是基本数据结构，通过连续存储实现高效随机访问"
        })

        mock_db = _make_mock_db_session()
        mock_unit = MagicMock()
        mock_unit.title = "数组基础"
        mock_unit.key_points = json.dumps(["连续存储", "随机访问"])

        mock_unit_result = MagicMock()
        mock_unit_result.scalar_one_or_none = MagicMock(return_value=mock_unit)
        mock_ann_result = MagicMock()
        mock_ann_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(side_effect=[mock_unit_result, mock_ann_result])

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        result = await service.generate_cornell_summary("unit-1", "数组是连续存储的数据结构")
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_cues_fallback_on_error(self, mock_llm):
        """LLM 失败时返回空线索"""
        mock_llm.chat_json = AsyncMock(side_effect=Exception("LLM error"))

        mock_db = _make_mock_db_session()
        mock_unit = MagicMock()
        mock_unit.title = "数组基础"
        mock_unit.key_points = json.dumps(["连续存储"])

        mock_unit_result = MagicMock()
        mock_unit_result.scalar_one_or_none = MagicMock(return_value=mock_unit)
        mock_ann_result = MagicMock()
        mock_ann_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(side_effect=[mock_unit_result, mock_ann_result])

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        result = await service.generate_cornell_cues("unit-1", "笔记内容")
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_summary_fallback_on_error(self, mock_llm):
        """LLM 失败时返回空总结"""
        mock_llm.chat_json = AsyncMock(side_effect=Exception("LLM error"))

        mock_db = _make_mock_db_session()
        mock_unit = MagicMock()
        mock_unit.title = "数组基础"
        mock_unit.key_points = json.dumps(["连续存储"])

        mock_unit_result = MagicMock()
        mock_unit_result.scalar_one_or_none = MagicMock(return_value=mock_unit)
        mock_ann_result = MagicMock()
        mock_ann_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(side_effect=[mock_unit_result, mock_ann_result])

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        result = await service.generate_cornell_summary("unit-1", "笔记内容")
        assert result == ""

    @pytest.mark.asyncio
    async def test_add_annotation_with_cornell(self, mock_llm):
        """添加康奈尔笔记注释"""
        mock_db = _make_mock_db_session()
        service = TeachingService(llm_client=mock_llm, db=mock_db)
        annotation = await service.add_annotation(
            user_id="user-1",
            unit_id="unit-1",
            annotation_type="cornell_note",
            content="笔记内容",
            cornell_cues=["线索1", "线索2"],
            cornell_summary="这是总结",
        )
        assert annotation.annotation_type == "cornell_note"
        assert annotation.cornell_cues == ["线索1", "线索2"]
        assert annotation.cornell_summary == "这是总结"
