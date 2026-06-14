package com.studyinghelper.mobile.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.studyinghelper.mobile.ui.theme.*

// ==================== 装饰组件 ====================

/**
 * 书签丝带装饰条
 */
@Composable
fun BookmarkRibbon(
    modifier: Modifier = Modifier,
    color: Color = BookmarkGreen
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(4.dp)
            .background(
                brush = Brush.horizontalGradient(
                    colors = listOf(color.copy(alpha = 0.7f), color)
                ),
                shape = RoundedCornerShape(bottomStart = 2.dp, bottomEnd = 2.dp)
            )
    )
}

/**
 * 纸张纹理背景（轻微噪点暗示）
 */
@Composable
fun PaperBackground(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(PaperWhite)
    ) {
        content()
    }
}

// ==================== 按钮组件 ====================

/**
 * 纸片按钮 - 主要按钮样式
 */
@Composable
fun PaperButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    backgroundColor: Color = CoffeeOrange,
    content: @Composable RowScope.() -> Unit
) {
    Button(
        onClick = onClick,
        modifier = modifier.height(44.dp),
        enabled = enabled,
        shape = RoundedCornerShape(22.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = backgroundColor,
            contentColor = Color.White,
            disabledContainerColor = backgroundColor.copy(alpha = 0.5f),
            disabledContentColor = Color.White.copy(alpha = 0.7f),
        ),
        elevation = ButtonDefaults.buttonElevation(
            defaultElevation = 2.dp,
            pressedElevation = 4.dp,
        ),
        content = content
    )
}

/**
 * 幽灵按钮 - 次要按钮样式
 */
@Composable
fun GhostButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    content: @Composable RowScope.() -> Unit
) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.height(44.dp),
        enabled = enabled,
        shape = RoundedCornerShape(22.dp),
        border = ButtonDefaults.outlinedButtonBorder.copy(
            brush = Brush.linearGradient(
                colors = listOf(InkBrown.copy(alpha = 0.6f), InkBrown.copy(alpha = 0.6f))
            )
        ),
        colors = ButtonDefaults.outlinedButtonColors(
            contentColor = InkBrown,
            disabledContentColor = InkBrown.copy(alpha = 0.4f),
        ),
        content = content
    )
}

// ==================== 进度条组件 ====================

/**
 * 墨水渐变进度条
 */
@Composable
fun InkProgressBar(
    progress: Float,
    modifier: Modifier = Modifier,
) {
    val clampedProgress = progress.coerceIn(0f, 1f)

    LinearProgressIndicator(
        progress = { clampedProgress },
        modifier = modifier
            .fillMaxWidth()
            .height(8.dp)
            .clip(RoundedCornerShape(4.dp)),
        color = InkBrown,
        trackColor = LightBrown,
    )
}

// ==================== 卡片组件 ====================

/**
 * 带书脊效果的书籍卡片
 */
@Composable
fun BookCardWithSpine(
    title: String,
    subtitle: String,
    progress: Float,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 12.dp)
        ) {
            // 书脊效果
            Box(
                modifier = Modifier
                    .width(6.dp)
                    .height(IntrinsicSize.Max)
                    .background(
                        brush = Brush.verticalGradient(
                            colors = listOf(InkBrown.copy(alpha = 0.8f), InkBrown)
                        ),
                        shape = RoundedCornerShape(topStart = 12.dp, bottomStart = 12.dp)
                    )
            )

            // 内容区
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = InkBrown,
                    maxLines = 2,
                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                )
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MediumBrown
                )
                InkProgressBar(progress = progress)
            }
        }
    }
}

/**
 * 编号圆圈
 */
@Composable
fun NumberCircle(
    number: Int,
    modifier: Modifier = Modifier,
    backgroundColor: Color = BookmarkGreen,
    textColor: Color = Color.White
) {
    Surface(
        modifier = modifier.size(28.dp),
        shape = CircleShape,
        color = backgroundColor
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                text = "$number",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = textColor
            )
        }
    }
}

/**
 * 要点卡片
 */
@Composable
fun KeyPointCard(
    number: Int,
    title: String,
    explanation: String? = null,
    examples: List<String> = emptyList(),
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                NumberCircle(number = number)
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = InkBrown
                )
            }

            if (explanation != null) {
                Text(
                    text = explanation,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MediumBrown
                )
            }

            if (examples.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        text = "示例：",
                        style = MaterialTheme.typography.labelSmall,
                        color = BookmarkGreen,
                        fontWeight = FontWeight.Medium
                    )
                    examples.forEach { example ->
                        Row(modifier = Modifier.padding(start = 4.dp)) {
                            Text(
                                text = "• ",
                                style = MaterialTheme.typography.bodySmall,
                                color = BookmarkGreen
                            )
                            Text(
                                text = example,
                                style = MaterialTheme.typography.bodySmall,
                                color = MediumBrown
                            )
                        }
                    }
                }
            }
        }
    }
}

/**
 * 概念卡片
 */
@Composable
fun ConceptCard(
    name: String,
    definition: String? = null,
    examples: List<String> = emptyList(),
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "📌",
                    style = MaterialTheme.typography.titleSmall
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = name,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = BookmarkGreen
                )
            }

            if (definition != null) {
                Text(
                    text = definition,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MediumBrown
                )
            }

            if (examples.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        text = "示例：",
                        style = MaterialTheme.typography.labelSmall,
                        color = BookmarkGreen,
                        fontWeight = FontWeight.Medium
                    )
                    examples.forEach { example ->
                        Row(modifier = Modifier.padding(start = 4.dp)) {
                            Text(
                                text = "• ",
                                style = MaterialTheme.typography.bodySmall,
                                color = BookmarkGreen
                            )
                            Text(
                                text = example,
                                style = MaterialTheme.typography.bodySmall,
                                color = MediumBrown
                            )
                        }
                    }
                }
            }
        }
    }
}

/**
 * 区块标题（带书签丝带装饰）
 */
@Composable
fun SectionTitleWithRibbon(
    title: String,
    modifier: Modifier = Modifier,
    ribbonColor: Color = BookmarkGreen
) {
    Column(modifier = modifier) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = InkBrown
        )
        Spacer(modifier = Modifier.height(4.dp))
        BookmarkRibbon(color = ribbonColor)
    }
}

/**
 * 欢迎卡片（带手写体风格）
 */
@Composable
fun WelcomeCard(
    title: String,
    subtitle: String,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = BookmarkGreen.copy(alpha = 0.1f)
        )
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                color = BookmarkGreen
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodyMedium,
                color = MediumBrown
            )
        }
    }
}
