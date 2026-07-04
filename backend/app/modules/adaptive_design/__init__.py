"""适应性教学设计模块（Adaptive Instructional Design, AID）

在 AI 学习完成、教学启动之间插入一层"教学设计"环节，分为三层：
- 宏观 Macro：跨章节把概念聚类成学习模块（Module），不机械按章节切分
- 微观 Micro：模块内小概念的教授计划（顺序、记忆/理解、合并、推迟）
- 动态 Replan：每模块结束后的查漏补缺

依赖方向单向：adaptive_design -> {knowledge_graph, ai_learning, review(mastery)}
teaching 不 import 本模块；router 层通过依赖注入拿 ordered_unit_ids。
"""
