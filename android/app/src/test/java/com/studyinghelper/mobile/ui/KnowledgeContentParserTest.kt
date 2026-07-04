package com.studyinghelper.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class KnowledgeContentParserTest {
    @Test
    fun parsesKeyPointsFromStringAndObjectItems() {
        val result = parseKeyPoints(
            """
            [
              "核心结论",
              {
                "title": "结构化要点",
                "explanation": "先理解定义",
                "examples": ["例子 A", " ", "例子 B"]
              },
              ""
            ]
            """.trimIndent()
        )

        assertEquals(2, result.size)
        assertEquals("核心结论", result[0].title)
        assertEquals("结构化要点", result[1].title)
        assertEquals("先理解定义", result[1].explanation)
        assertEquals(listOf("例子 A", "例子 B"), result[1].examples)
    }

    @Test
    fun parsesConceptsFromStringAndObjectItems() {
        val result = parseConcepts(
            """
            [
              "抽象概念",
              {
                "name": "结构化概念",
                "definition": "用于说明知识结构",
                "examples": ["定义例子"]
              },
              {"definition": "缺少名称会被忽略"}
            ]
            """.trimIndent()
        )

        assertEquals(2, result.size)
        assertEquals("抽象概念", result[0].name)
        assertEquals("结构化概念", result[1].name)
        assertEquals("用于说明知识结构", result[1].definition)
        assertEquals(listOf("定义例子"), result[1].examples)
    }

    @Test
    fun returnsEmptyListForInvalidContent() {
        assertTrue(parseKeyPoints("not json").isEmpty())
        assertTrue(parseConcepts("{}").isEmpty())
    }
}
