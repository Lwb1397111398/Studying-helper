package com.studyinghelper.mobile.ui.theme

import androidx.compose.ui.graphics.Color

// 笔记本风格颜色系统
// 参考：泛黄纸张 + 墨水 + 书签丝带 + 咖啡渍

// 背景色系
val PaperWhite = Color(0xFFFDF8F3)        // 泛黄纸张（主背景）
val CardBackground = Color(0xFFFAF6F1)    // 卡片背景（纸张叠加）
val SurfaceVariant = Color(0xFFF5EDE6)    // 表面变体（更深的纸张）

// 主色系
val InkBrown = Color(0xFF5D4037)          // 墨水（主文字、标题）
val MediumBrown = Color(0xFF8D6E63)       // 中棕（次级文字）
val LightBrown = Color(0xFFD7CCC8)        // 浅棕（占位符、边框）
val PaleBrown = Color(0xFFBCAAA4)         // 淡棕（禁用状态）

// 强调色系
val BookmarkGreen = Color(0xFF6B7B3A)     // 书签丝带（主强调、成功）
val CoffeeOrange = Color(0xFFD4915E)      // 咖啡渍（辅助、高亮）
val Amber = Color(0xFFFF8F00)            // 琥珀（警告、待办）

// 语义颜色
val Success = BookmarkGreen               // 成功/掌握
val InProgress = CoffeeOrange            // 进行中
val Warning = Amber                      // 待办/提醒
val Error = Color(0xFFC62828)             // 错误（暖红）

// 传统颜色（兼容旧代码）
val Purple80 = Color(0xFFD0BCFF)
val PurpleGrey80 = Color(0xFFCCC2DC)
val Pink80 = Color(0xFFEFB8C8)
val Purple40 = Color(0xFF6650a4)
val PurpleGrey40 = Color(0xFF625b71)
val Pink40 = Color(0xFF7D5260)
