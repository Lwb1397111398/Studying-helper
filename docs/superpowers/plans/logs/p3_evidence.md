# P3a 删除证据留痕（logs/p3_evidence.md）

生成时间：2026-10-28。回滚总则：每批独立 commit，`git revert <hash>` 即可整体回退。

## B1 死查询/死变量（commit bd504a1）

### 1. knowledge_graph/service.py update_unit_graph 内 existing_edges（原 419-431 行）
- 删除前上下文：`existing_edges_result = await self.db.execute(select(KGEdgeModel).where(KGEdgeModel.source_id.in_([n.id for n in existing_nodes])))` + 列表推导构建 `existing_edges = [KGEdge(...) for e in existing_edges_result.scalars().all()]`
- 删除后：整块移除，前后文为 existing_nodes 构建块与「# 3. 为新单元创建节点」注释
- rg 前后：删除前 `rg existing_edges app/` → 仅 service.py:419,424,430（定义+构建自身）；删除后 → 0 命中
- 三查：①无后续读写（rg 实证）；②查询点前仅有显式 Core delete 语句（非 pending ORM 对象），查询后至函数尾部 `await self.db.flush()` 之间无其他依赖 autoflush 的查询；③有 HTTP 端点（router.py:230）→ API 级对比
- API 级对比：scripts/p3_b1_api_diff.py（固定 fixture，build→update→GET 全链，随机 uuid 规范化为 label 基确定性 id；脚本先自复现两次验证确定性）。删除前后响应 diff 完全一致（logs/p3_b1_api_before.json vs p3_b1_api_after.json）
- 测试：knowledge_graph + exporters 93 passed

### 2/3. cornell_exporter.py:32 / markdown_exporter.py:32 chapter_map
- 删除前上下文：`chapter_map = {c['id']: c for c in chapters}`（纯本地 dict，无 IO）
- rg 前后：删除前仅各自定义行 1 处；删除后 0 命中
- 金样对比：scripts/p3_b1_golden_export.py 固定输入（2 章节 2 单元 2 掌握度），导出文本时间戳规范化后 diff——完全一致（logs/p3_b1_golden_before/ vs _after/）

## B2 死变量（本 commit）

RHS 副作用判定：以下各项 RHS 均为纯表达式（比较/切片/comprehension/dict.get），整行删除。

| # | 文件:行 | 删除内容 | 判定 |
|---|---|---|---|
| ① | readiness.py:43-44 | `supported = ...` / `valid_refs = all(...) if ... else False` | 与后文 `ok` 计算重复（后文注释 # Prefer explicit support_status 即重新实现同逻辑），纯表达式 |
| ② | txt_parser.py:141 | `in_toc_section = False` | 赋值后全文无使用 |
| ③ | book_service.py:112-114 | `chapter_ids_result = await self.db.execute(select(ChapterModel.id)...)` 整块 | **连锁死查询**：删除 `chapter_ids` 取值行后查询亦无消费方。RHS 有副作用（DB 查询），按 B1 死查询三查流程处理：①无后续读写；②查询前仅 get_book 的 select（无 pending 写），后续 ku_ids 查询保留 autoflush 点；③delete_book 有既有级联测试 test_delete_book_cascades 锁行为。注释「2次查询」改为「1次查询」 |
| ④⑤ | incremental_sync.py:444-445 | `node_ids = ...` / `session_ids = ...` | set comprehension 纯表达式，验证逻辑只用 book/chapter/unit_ids |
| ⑥ | pipeline.py:66 | `rev_id = ctx.get("document_revision_id") or ""` | dict.get 纯表达式 |
| ⑦ | knowledge_splitter/router.py:185 | `except Exception as e:` → `except Exception:` | e 未使用 |
| ⑧ | fsrs.py:156 | （P1 已随改点消除） | 勾掉 |

### 调查类（保留，not-applicable）
- style_analyzer.py:159 / style_analyzer_v2.py:293 `total_minutes = sum(s.total_minutes or 0 for s in stats)`
- 判定：两处同型，学习时长聚合从未参与任何输出维度（reading/practice 权重只用 units/reviews/tests）。疑似「时间偏好」维度半成品，但现有功能行为自洽、无法用失败测试证明丢逻辑。按计划案「调查类证明不了 → 保留」处理，记 not-applicable；**豁免于 pyflakes 0 要求**。两处属 learning_plan 模块，与 B2 批次其他文件无耦合。

## B4 f-string（本 commit）

| 文件:行 | 删除前 | 删除后 | 占位符检查 |
|---|---|---|---|
| pipeline.py:79 | `f"本单元的核心内容是什么？"` | `"本单元的核心内容是什么？"` | 无 {} |
| ai_learning/service.py:455 | `f"Reduce 整合结果质量不合格，重试..."` | 同文去 f | 无 {} |
| ai_learning/service.py:492 | `f"最终整合结果质量不合格，重试..."` | 同文去 f | 无 {} |

## 验证汇总
- pyflakes 目标诊断：B1 三处 + B2 七处 + B4 三处全部归 0；白名单外无新增诊断
  （book_service/os、splitter/ParsedDocument、splitter/SplitStats、incremental_sync/datetime.timezone、
  ai_learning/LearningProgress+LearningStatus、style_analyzer/Optional、cornell/Optional 等
  均为基线既有未使用导入，属 C1 可选范围）
- 模块测试：受影响 6 模块 134 passed；全量 522 passed（与 P2 后基线一致，无回归）
- 本批回滚：`git revert <本commit hash>`
