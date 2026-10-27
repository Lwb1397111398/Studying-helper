"""P3a-B1 金样对比：cornell/markdown 导出器删除 chapter_map 死变量前后的规范化文本 diff。

时间戳行（导出时间）先替换为占位符再比较。
用法：python scripts/p3_b1_golden_export.py <输出目录>
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.review.exporters import export_markdown
from app.modules.review.exporters.cornell_exporter import export_cornell_notes

CHAPTERS = [
    {"id": "ch-1", "title": "基础", "chapter_number": 1},
    {"id": "ch-2", "title": "进阶", "chapter_number": 2},
]
UNITS = [
    {"id": "u-1", "chapter_id": "ch-1", "title": "数组", "summary": "数组是基本数据结构",
     "key_points": ["连续存储", "随机访问"]},
    {"id": "u-2", "chapter_id": "ch-2", "title": "二叉树", "summary": "树结构",
     "key_points": ["递归遍历"]},
]
MASTERY = {"u-1": {"score": 0.9, "level": "mastered"}, "u-2": {"score": 0.5, "level": "familiar"}}


def _norm(text: str) -> str:
    return re.sub(r"导出时间：.*", "导出时间：<NORMALIZED>", text)


def main():
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "markdown.txt").write_text(_norm(export_markdown("金样书", CHAPTERS, UNITS, MASTERY).content), encoding="utf-8")
    (out_dir / "cornell.txt").write_text(_norm(export_cornell_notes("金样书", CHAPTERS, UNITS, MASTERY).content), encoding="utf-8")
    print(f"golden -> {out_dir}")


if __name__ == "__main__":
    main()
