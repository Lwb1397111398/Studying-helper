# Step 7 回报：大单元 map-reduce 精读

## ① 切分策略样例 + reduce 输入输出样例

**切分策略**（chunk_unit_text）：
- 按标题/段落边界切，目标 ≤6000 字
- 大单元 >8000 字时拆成多块，每块单独 LLM 提取 claims
- 样例：长文本被切成 4 块，每块提取 1-3 个 claims

**reduce 输入输出**：
- 输入：各 chunk 的 claims + chapter_summary + book_overview
- 输出：合并后的 claims（去重后按 role 排序）、one_sentence_summary、key_points

**样例**（reduce 产出）：
```json
{
  "claims": [
    {"text": "反向传播是链式求导", "role_in_book": "key_mechanism", "mastery_check": "能说明链式求导"},
    {"text": "梯度是方向导数", "role_in_book": "supporting_detail", "mastery_check": "能复述梯度定义"},
    {"text": "残差连接是残差", "role_in_book": "core_thesis_support", "mastery_check": "能解释残差连接在全书中的作用"}
  ],
  "one_sentence_summary": "反向传播、梯度、残差连接是神经网络的核心机制",
  "key_points": ["反向传播是链式求导", "梯度是方向导数", "残差连接是残差"],
  "prerequisites": [],
  "partial": false
}
```

## ② fallback 验证

| 场景 | 行为 |
| --- | --- |
| ≤8000 字 | 老单次路径，claims 与之前一致 |
| 部分 chunk 失败 | 成功块合并产出，仍有 partial 标记 |
| reduce LLM 失败 | 程序兜底：合并 claims + 默认 supporting_detail + 从最强 claim 生成 mastery_check |
| 无 LLM | 现有 rule-based fallback 不变 |

## ③ 验收对照

| 标准 | 结果 |
| --- | --- |
| 1. ~2 万字单元覆盖首/中/尾 claims | ✅ test_mapreduce_large_unit_coverage |
| 2. ≤8000 字回归老路径 | ✅ 所有现有理解测试全绿 |
| 3. 部分 chunk 失败仍合并 | ✅ test_partial_chunk_fail |
| 4. reduce 失败程序兜底 | ✅ test_reduce_fallback |
| 5. 无 LLM 路径 | ✅ test_no_llm_fallback |
| 6. concept_harvest 钩子正常 | ✅ 现有理解测试 + 新 map-reduce 测试 |

### 主要文件
- `learning_assets/understanding.py`（map-reduce 核心）
- `learning_assets/concept_harvest.py`（hook 更新）
- `ai_learning/schemas.py`（BookDeepOverview 兼容）
- `tests/test_mapreduce_large_unit.py`（新增覆盖测试）

### 本步未做
Android / 同步包 / 概念消歧（正式挂起）。

---

**Step 7 完成。** map-reduce 落地，大单元质量底线解决。建议跑一次 `build_exe.bat` 重新打包 → 项目交付。最终形态：一个 68MB 的 exe + data/ 目录，导入书籍即可深度精读学习，不配 LLM 也能全程 fallback 使用。