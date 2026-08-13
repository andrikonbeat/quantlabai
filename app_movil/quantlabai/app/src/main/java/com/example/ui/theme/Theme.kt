package com.example.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkColorScheme = darkColorScheme(
    primary = ElectricCyan,
    onPrimary = Color.White,
    primaryContainer = GraphiteSurfaceVariant,
    onPrimaryContainer = ElectricCyan,
    secondary = ElectricViolet,
    onSecondary = Color.White,
    secondaryContainer = GraphiteSurfaceVariant,
    onSecondaryContainer = ElectricViolet,
    tertiary = StatusGreen,
    onTertiary = Color.White,
    background = GraphiteBackground,
    onBackground = TextPrimary,
    surface = GraphiteSurface,
    onSurface = TextPrimary,
    surfaceVariant = GraphiteSurfaceVariant,
    onSurfaceVariant = TextSecondary,
    outline = GraphiteBorder,
    outlineVariant = GraphiteBorder
)

@Composable
fun QuantLabTheme(
    darkTheme: Boolean = true, // Dark-first experience
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = Typography,
        content = content
    )
}

@Composable
fun MyApplicationTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit
) {
    QuantLabTheme(darkTheme = true, content = content)
}

