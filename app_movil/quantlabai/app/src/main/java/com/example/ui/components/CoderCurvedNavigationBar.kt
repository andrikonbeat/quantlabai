package com.example.ui.components

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.ExperimentalAnimationApi
import androidx.compose.animation.core.*
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.with
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.Screen
import com.example.ui.theme.*

class CurvedDockShape(
    private val activeIndexFraction: Float,
    private val itemCount: Int = 5,
    private val cornerRadiusPx: Float,
    private val cutoutRadiusPx: Float,
    private val cutoutDepthPx: Float
) : Shape {
    override fun createOutline(
        size: Size,
        layoutDirection: LayoutDirection,
        density: Density
    ): Outline {
        val path = Path().apply {
            val itemWidth = size.width / itemCount
            val cx = itemWidth * activeIndexFraction + itemWidth / 2f

            val notchLeft = cx - cutoutRadiusPx
            val notchRight = cx + cutoutRadiusPx

            // Dynamic corner radius so cutout blends seamlessly into screen edges without corner collisions
            val leftCorner = if (notchLeft < cornerRadiusPx) maxOf(0f, notchLeft) else cornerRadiusPx
            val rightCorner = if (notchRight > size.width - cornerRadiusPx) maxOf(0f, size.width - notchRight) else cornerRadiusPx

            // Control points for smooth Bezier curves
            val cp1X = (notchLeft + cutoutRadiusPx * 0.45f).coerceIn(0f, size.width)
            val cp2X = (cx - cutoutRadiusPx * 0.45f).coerceIn(0f, size.width)
            val cp3X = (cx + cutoutRadiusPx * 0.45f).coerceIn(0f, size.width)
            val cp4X = (notchRight - cutoutRadiusPx * 0.45f).coerceIn(0f, size.width)
            val rightEnd = notchRight.coerceIn(0f, size.width)

            // Path starting from top left
            if (leftCorner > 0f) {
                moveTo(0f, leftCorner)
                quadraticTo(0f, 0f, leftCorner, 0f)
            } else {
                moveTo(0f, 0f)
            }

            if (notchLeft > leftCorner) {
                lineTo(notchLeft, 0f)
            }

            // Left half of cutout
            cubicTo(
                cp1X, 0f,
                cp2X, cutoutDepthPx,
                cx, cutoutDepthPx
            )

            // Right half of cutout
            cubicTo(
                cp3X, cutoutDepthPx,
                cp4X, 0f,
                rightEnd, 0f
            )

            if (rightEnd < size.width - rightCorner) {
                lineTo(size.width - rightCorner, 0f)
            }

            if (rightCorner > 0f) {
                quadraticTo(size.width, 0f, size.width, rightCorner)
            } else {
                lineTo(size.width, 0f)
            }

            // Right edge down, bottom edge across, left edge back up
            lineTo(size.width, size.height)
            lineTo(0f, size.height)
            lineTo(0f, if (leftCorner > 0f) leftCorner else 0f)

            close()
        }
        return Outline.Generic(path)
    }
}

@OptIn(ExperimentalAnimationApi::class)
@Composable
fun CoderCurvedNavigationBar(
    items: List<Screen>,
    currentRoute: String?,
    onItemSelected: (Screen) -> Unit,
    modifier: Modifier = Modifier
) {
    val selectedIndex = remember(currentRoute) {
        val idx = items.indexOfFirst { it.route == currentRoute }
        if (idx >= 0) idx else 0
    }

    // Smooth fluid physics spring transition without shape distortion artifacts
    val animatedIndex by animateFloatAsState(
        targetValue = selectedIndex.toFloat(),
        animationSpec = spring(
            stiffness = 280f,
            dampingRatio = 0.72f
        ),
        label = "dock_active_index"
    )

    val density = LocalDensity.current
    val cornerRadiusPx = with(density) { 16.dp.toPx() }
    val cutoutRadiusPx = with(density) { 46.dp.toPx() } // Spacious cutout width
    val cutoutDepthPx = with(density) { 32.dp.toPx() }  // Spacious cutout depth

    val curvedShape = remember(
        animatedIndex, items.size, cornerRadiusPx, cutoutRadiusPx, cutoutDepthPx
    ) {
        CurvedDockShape(
            activeIndexFraction = animatedIndex,
            itemCount = items.size,
            cornerRadiusPx = cornerRadiusPx,
            cutoutRadiusPx = cutoutRadiusPx,
            cutoutDepthPx = cutoutDepthPx
        )
    }

    Box(
        modifier = modifier
            .fillMaxWidth()
            .navigationBarsPadding()
            .height(84.dp)
            .testTag("coder_curved_nav_bar"),
        contentAlignment = Alignment.BottomCenter
    ) {
        // Dark Cyber Blue Dock Container with spacious cutout
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(62.dp)
                .shadow(12.dp, curvedShape, spotColor = Color(0xFF003366), ambientColor = Color.Black)
                .background(Color(0xFF182535), shape = curvedShape)
                .border(1.dp, Color(0xFF2E4663), shape = curvedShape)
        )

        // Floating Active Circle Indicator perfectly synchronized with cutout
        BoxWithConstraints(
            modifier = Modifier
                .fillMaxWidth()
                .height(84.dp)
        ) {
            val totalWidth = maxWidth
            val itemWidth = totalWidth / items.size
            val activeCircleSize = 42.dp
            val activeXOffset = itemWidth * animatedIndex + (itemWidth - activeCircleSize) / 2f

            // Floating Green Active Circle with generous space inside the cutout
            Box(
                modifier = Modifier
                    .offset(x = activeXOffset, y = 3.dp)
                    .size(activeCircleSize)
                    .shadow(10.dp, CircleShape, spotColor = StatusGreen, ambientColor = StatusGreen)
                    .background(StatusGreen, shape = CircleShape)
                    .border(2.dp, Color(0xFF030507), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                val activeScreen = items.getOrNull(selectedIndex) ?: items[0]
                AnimatedContent(
                    targetState = activeScreen,
                    transitionSpec = {
                        (fadeIn(animationSpec = tween(150)) + scaleIn(initialScale = 0.8f)) with
                                (fadeOut(animationSpec = tween(150)) + scaleOut(targetScale = 0.8f))
                    },
                    label = "icon_transition"
                ) { screen ->
                    Icon(
                        imageVector = screen.icon,
                        contentDescription = screen.title,
                        tint = Color(0xFF030507),
                        modifier = Modifier.size(22.dp)
                    )
                }
            }

            // Items Row (High-Contrast Monospace Labels & Crisp Icons)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(60.dp)
                    .align(Alignment.BottomCenter),
                verticalAlignment = Alignment.CenterVertically
            ) {
                items.forEachIndexed { index, screen ->
                    val isSelected = index == selectedIndex
                    val interactionSource = remember { MutableInteractionSource() }

                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .clickable(
                                interactionSource = interactionSource,
                                indication = null
                            ) {
                                onItemSelected(screen)
                            }
                            .testTag("nav_${screen.route}"),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        if (!isSelected) {
                            Icon(
                                imageVector = screen.icon,
                                contentDescription = screen.title,
                                tint = Color(0xFFB5CDE3),
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = when (screen.route) {
                                    "dashboard" -> "DASH"
                                    "campaigns" -> "CAMP"
                                    "chat" -> "CHAT"
                                    "agents" -> "AGNT"
                                    else -> "MORE"
                                },
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.SemiBold,
                                color = Color(0xFF8FAECB)
                            )
                        } else {
                            Spacer(modifier = Modifier.height(22.dp))
                            Text(
                                text = when (screen.route) {
                                    "dashboard" -> "[ DASH ]"
                                    "campaigns" -> "[ CAMP ]"
                                    "chat" -> "[ CHAT ]"
                                    "agents" -> "[ AGNT ]"
                                    else -> "[ MORE ]"
                                },
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                color = StatusGreen
                            )
                        }
                    }
                }
            }
        }
    }
}

