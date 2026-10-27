"""P2 埋雷修复回归：字符串注解引用的未导入名在 get_type_hints 下必须可解析。

修复前三处 `typing.get_type_hints` 一碰即 NameError：
- AIDService.replan_next_module 的 StageFeedback/ReplanResult 注解
- create_fsrs_state_from_mastery_record 的 MasteryRecordModel 注解
本测试显式 import 目标模块后逐一断言可解析且 identity 与源模块一致。
"""

import typing

from app.modules.adaptive_design import schemas as aid_schemas
from app.modules.adaptive_design.service import AIDService
from app.modules.review import fsrs as review_fsrs


def test_replan_next_module_annotations_resolve():
    hints = typing.get_type_hints(AIDService.replan_next_module)
    assert "feedback" in hints
    assert "return" in hints
    # identity：与 schemas 模块中的对象是同一个类，不是重复导入的副本
    assert hints["feedback"] is aid_schemas.StageFeedback
    assert hints["return"] is aid_schemas.ReplanResult


def test_create_fsrs_state_annotations_resolve():
    hints = typing.get_type_hints(review_fsrs.create_fsrs_state_from_mastery_record)
    assert "record" in hints
    from app.db.models import MasteryRecordModel

    assert hints["record"] is MasteryRecordModel
