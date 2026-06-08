package com.studyinghelper.mobile.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// 笔记本风格浅色主题
private val WarmLightColorScheme = lightColorScheme(
    primary = BookmarkGreen,
    onPrimary = androidx.compose.ui.graphics.Color.White,
    primaryContainer = BookmarkGreen.copy(alpha = 0.12f),
    onPrimaryContainer = BookmarkGreen,
    secondary = CoffeeOrange,
    onSecondary = androidx.compose.ui.graphics.Color.White,
    secondaryContainer = CoffeeOrange.copy(alpha = 0.12f),
    onSecondaryContainer = CoffeeOrange,
    tertiary = Amber,
    onTertiary = androidx.compose.ui.graphics.Color.White,
    background = PaperWhite,
    onBackground = InkBrown,
    surface = CardBackground,
    onSurface = InkBrown,
    surfaceVariant = SurfaceVariant,
    onSurfaceVariant = MediumBrown,
    outline = LightBrown,
    outlineVariant = PaleBrown,
    error = Error,
    onError = androidx.compose.ui.graphics.Color.White,
)

// 笔记本风格深色主题（暖色调深色）
private val WarmDarkColorScheme = darkColorScheme(
    primary = BookmarkGreen.copy(alpha = 0.8f),
    onPrimary = androidx.compose.ui.graphics.Color.White,
    primaryContainer = BookmarkGreen.copy(alpha = 0.3f),
    onPrimaryContainer = BookmarkGreen.copy(alpha = 0.9f),
    secondary = CoffeeOrange.copy(alpha = 0.8f),
    onSecondary = androidx.compose.ui.graphics.Color.White,
    secondaryContainer = CoffeeOrange.copy(alpha = 0.3f),
    onSecondaryContainer = CoffeeOrange.copy(alpha = 0.9f),
    tertiary = Amber.copy(alpha = 0.8f),
    onTertiary = androidx.compose.ui.graphics.Color.White,
    background = androidx.compose.ui.graphics.Color(0xFF1A1714),
    onBackground = androidx.compose.ui.graphics.Color(0xFFE8E0D8),
    surface = androidx.compose.ui.graphics.Color(0xFF252019),
    onSurface = androidx.compose.ui.graphics.Color(0xFFE8E0D8),
    surfaceVariant = androidx.compose.ui.graphics.Color(0xFF302A22),
    onSurfaceVariant = androidx.compose.ui.graphics.Color(0xFFD0C5B8),
    outline = androidx.compose.ui.graphics.Color(0xFF5A4E42),
    outlineVariant = androidx.compose.ui.graphics.Color(0xFF3D342B),
    error = androidx.compose.ui.graphics.Color(0xFFFFB4AB),
    onError = androidx.compose.ui.graphics.Color(0xFF690005),
)

@Composable
fun StudyingHelperTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false, // 禁用动态颜色，使用固定的暖色调
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> WarmDarkColorScheme
        else -> WarmLightColorScheme
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
