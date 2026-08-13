package com.example.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.R
import com.example.data.model.*
import com.example.ui.theme.*

@Composable
fun LivePulseIndicator(
    modifier: Modifier = Modifier,
    color: Color = StatusGreen,
    sizeDp: Int = 10
) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(900, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "alphaPulse"
    )
    val scale by infiniteTransition.animateFloat(
        initialValue = 0.85f,
        targetValue = 1.35f,
        animationSpec = infiniteRepeatable(
            animation = tween(900, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scalePulse"
    )

    Box(
        modifier = modifier.size((sizeDp * 1.5).dp),
        contentAlignment = Alignment.Center
    ) {
        Box(
            modifier = Modifier
                .size((sizeDp * scale).dp)
                .background(color.copy(alpha = alpha * 0.35f), CircleShape)
        )
        Box(
            modifier = Modifier
                .size(sizeDp.dp)
                .background(color, CircleShape)
        )
    }
}

@Composable
fun StatusBadge(
    text: String,
    statusColor: Color,
    bgColor: Color,
    modifier: Modifier = Modifier,
    showDot: Boolean = true
) {
    Surface(
        modifier = modifier.clip(RoundedCornerShape(2.dp)),
        color = bgColor,
        border = BorderStroke(1.dp, statusColor.copy(alpha = 0.5f))
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center
        ) {
            if (showDot) {
                Text(
                    text = "●",
                    color = statusColor,
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.width(4.dp))
            }
            Text(
                text = "[ ${text.uppercase()} ]",
                color = statusColor,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
fun ProgressBar(
    progress: Float,
    modifier: Modifier = Modifier,
    barColor: Color = ElectricCyan,
    trackColor: Color = GraphiteSurfaceVariant
) {
    val clampedProgress = progress.coerceIn(0f, 1f)
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(6.dp)
            .background(trackColor, RoundedCornerShape(2.dp))
            .border(1.dp, GraphiteBorder, RoundedCornerShape(2.dp))
    ) {
        Box(
            modifier = Modifier
                .fillMaxHeight()
                .fillMaxWidth(clampedProgress)
                .background(barColor, RoundedCornerShape(2.dp))
        )
    }
}


@Composable
fun HealthCard(
    systemHealth: SystemHealth,
    modifier: Modifier = Modifier
) {
    var expanded by remember { mutableStateOf(false) }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp))
            .clickable { expanded = !expanded }
            .testTag("health_card"),
        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .background(StatusGreen, CircleShape)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "System Health",
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    StatusBadge(
                        text = "${systemHealth.totalOperational}/5 Operational",
                        statusColor = StatusGreen,
                        bgColor = StatusGreenBg
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Icon(
                        imageVector = if (expanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                        contentDescription = "Expand health status",
                        tint = TextSecondary,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            AnimatedVisibility(visible = expanded) {
                Column(modifier = Modifier.padding(top = 14.dp)) {
                    HorizontalDivider(color = GraphiteBorder, thickness = 1.dp)
                    Spacer(modifier = Modifier.height(12.dp))

                    HealthItem(name = "OpenCode", online = systemHealth.openCodeOnline, detail = "Session #2401 active")
                    HealthItem(name = "Orchestrator", online = systemHealth.orchestratorRunning, detail = "Master process PID 8102")
                    HealthItem(name = "StrategyQuant X", online = systemHealth.sqxOnline, detail = "5,000 gen target queue")
                    HealthItem(name = "Data Pipeline", online = systemHealth.dataPipelineOnline, detail = "Dukascopy EURUSD tick feed")
                    HealthItem(name = "Database", online = systemHealth.databaseOnline, detail = "Local Room DB active")

                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "CPU: ${systemHealth.cpuUsagePct}% | RAM: ${systemHealth.ramUsagePct}% | Storage: ${systemHealth.storageUsagePct}%",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace
                        )
                        Text(
                            text = "Workers: ${systemHealth.activeWorkers}/${systemHealth.totalWorkers}",
                            color = ElectricCyan,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun HealthItem(name: String, online: Boolean, detail: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .background(if (online) StatusGreen else StatusRed, CircleShape)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = name,
                color = TextPrimary,
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium
            )
        }
        Text(
            text = detail,
            color = TextSecondary,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
fun CampaignCard(
    campaign: Campaign,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
            .testTag("campaign_card_${campaign.id}"),
        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "${campaign.asset} ${campaign.timeframe}",
                        color = ElectricCyan,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                    Text(
                        text = campaign.name,
                        color = TextPrimary,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
                StatusBadge(
                    text = campaign.status.name,
                    statusColor = when (campaign.status) {
                        CampaignStatus.ACTIVE -> StatusBlue
                        CampaignStatus.ATTENTION -> StatusAmber
                        CampaignStatus.COMPLETED -> StatusGreen
                        CampaignStatus.PAUSED -> StatusGray
                        CampaignStatus.FAILED -> StatusRed
                        CampaignStatus.ARCHIVED -> StatusGray
                    },
                    bgColor = when (campaign.status) {
                        CampaignStatus.ACTIVE -> StatusBlueBg
                        CampaignStatus.ATTENTION -> StatusAmberBg
                        CampaignStatus.COMPLETED -> StatusGreenBg
                        CampaignStatus.PAUSED -> StatusGrayBg
                        CampaignStatus.FAILED -> StatusRedBg
                        CampaignStatus.ARCHIVED -> StatusGrayBg
                    }
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Progress bar
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Current Stage: ${campaign.currentStage.name}",
                    color = TextSecondary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = "${campaign.progressPct}%",
                    color = TextPrimary,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
            LinearProgressIndicator(
                progress = { campaign.progressPct / 100f },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(6.dp)
                    .clip(RoundedCornerShape(3.dp)),
                color = ElectricCyan,
                trackColor = GraphiteSurfaceVariant
            )

            Spacer(modifier = Modifier.height(14.dp))

            // Footer metrics
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.SmartToy,
                        contentDescription = "Agents",
                        tint = TextSecondary,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = "${campaign.activeAgents} active · ${campaign.waitingAgents} waiting",
                        color = TextSecondary,
                        fontSize = 12.sp
                    )
                }

                Text(
                    text = "${campaign.generatedCount} strats (${campaign.passedFiltersCount} passed)",
                    color = StatusGreen,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    fontFamily = FontFamily.Monospace
                )
            }
        }
    }
}

@Composable
fun AgentCard(
    agent: Agent,
    onDetailClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val (statusColor, statusBg) = when (agent.status) {
        AgentStatus.RUNNING -> StatusBlue to StatusBlueBg
        AgentStatus.WAITING -> StatusAmber to StatusAmberBg
        AgentStatus.IDLE -> StatusGray to StatusGrayBg
        AgentStatus.ERROR -> StatusRed to StatusRedBg
        AgentStatus.PAUSED -> StatusGray to StatusGrayBg
    }

    val isRunning = agent.status == AgentStatus.RUNNING
    val borderStroke = if (isRunning) {
        BorderStroke(1.dp, Brush.horizontalGradient(listOf(StatusBlue.copy(alpha = 0.8f), ElectricCyan.copy(alpha = 0.8f))))
    } else {
        BorderStroke(1.dp, GraphiteBorder)
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(borderStroke, RoundedCornerShape(12.dp))
            .clickable(onClick = onDetailClick)
            .testTag("agent_card_${agent.id}"),
        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .background(GraphiteSurfaceVariant, CircleShape)
                            .border(1.dp, statusColor.copy(alpha = 0.5f), CircleShape),
                        contentAlignment = Alignment.Center
                    ) {
                        if (isRunning) {
                            LivePulseIndicator(sizeDp = 12, color = StatusBlue)
                        } else {
                            Icon(
                                imageVector = Icons.Default.Memory,
                                contentDescription = agent.name,
                                tint = statusColor,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            text = agent.name,
                            color = TextPrimary,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = agent.role,
                            color = TextSecondary,
                            fontSize = 12.sp
                        )
                    }
                }
                StatusBadge(
                    text = agent.status.name,
                    statusColor = statusColor,
                    bgColor = statusBg
                )
            }

            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = agent.currentTask,
                color = TextPrimary,
                fontSize = 13.sp,
                maxLines = 2
            )

            Spacer(modifier = Modifier.height(10.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "Campaign: ${agent.campaignName}",
                    color = ElectricCyan,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    text = "Runtime: ${agent.runtime}",
                    color = TextMuted,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        }
    }
}

@Composable
fun StrategyCard(
    strategy: Strategy,
    onDetailClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val (statusColor, statusBg) = when (strategy.status) {
        StrategyStatus.CANDIDATE -> StatusAmber to StatusAmberBg
        StrategyStatus.VALIDATED -> StatusGreen to StatusGreenBg
        StrategyStatus.LIVE -> StatusBlue to StatusBlueBg
        StrategyStatus.DEGRADED -> StatusRed to StatusRedBg
        StrategyStatus.REPLACEMENT_READY -> ElectricCyan to CyanGlow
        StrategyStatus.REJECTED -> StatusGray to StatusGrayBg
    }

    val isHighPerformance = strategy.score >= 85 || strategy.status == StrategyStatus.LIVE || strategy.status == StrategyStatus.REPLACEMENT_READY
    val borderStroke = if (isHighPerformance) {
        BorderStroke(1.dp, Brush.horizontalGradient(listOf(statusColor.copy(alpha = 0.8f), ElectricCyan.copy(alpha = 0.8f))))
    } else {
        BorderStroke(1.dp, GraphiteBorder)
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(borderStroke, RoundedCornerShape(12.dp))
            .clickable(onClick = onDetailClick)
            .testTag("strategy_card_${strategy.id}"),
        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        color = ElectricCyan.copy(alpha = 0.15f),
                        shape = RoundedCornerShape(6.dp)
                    ) {
                        Text(
                            text = "SCORE ${strategy.score}",
                            color = ElectricCyan,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            fontFamily = FontFamily.Monospace
                        )
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "${strategy.codeNumber} (${strategy.asset} ${strategy.timeframe})",
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
                StatusBadge(text = strategy.status.name, statusColor = statusColor, bgColor = statusBg)
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        MetricColumn(label = "Net Profit", value = strategy.netProfit, valueColor = StatusGreen)
                        MetricColumn(label = "Sharpe", value = String.format("%.2f", strategy.sharpeRatio))
                        MetricColumn(label = "Max DD", value = "${strategy.maxDrawdownPct}%", valueColor = StatusRed)
                        MetricColumn(label = "PF", value = String.format("%.2f", strategy.profitFactor))
                    }
                }
                Spacer(modifier = Modifier.width(12.dp))
                // Live Sparkline Chart
                SparklineChart(
                    modifier = Modifier
                        .width(80.dp)
                        .height(36.dp),
                    color = if (strategy.netProfit.startsWith("-")) StatusRed else StatusGreen,
                    points = listOf(10f, 12f, 15f, 14f, 19f, 25f, 22f, 28f, 32f, 38f)
                )
            }

            Spacer(modifier = Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    TestChip(name = "WF", pass = strategy.walkForwardPass)
                    TestChip(name = "MC", pass = strategy.monteCarloPass)
                    TestChip(name = "Param", pass = strategy.parameterStabilityPass)
                    TestChip(name = "Regime", pass = strategy.marketRegimePass)
                }

                Text(
                    text = strategy.correlationStatus,
                    color = TextSecondary,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        }
    }
}

@Composable
private fun MetricColumn(label: String, value: String, valueColor: Color = TextPrimary) {
    Column {
        Text(text = label, color = TextMuted, fontSize = 11.sp)
        Text(
            text = value,
            color = valueColor,
            fontSize = 13.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun TestChip(name: String, pass: Boolean) {
    Surface(
        color = if (pass) StatusGreenBg else StatusRedBg,
        shape = RoundedCornerShape(4.dp)
    ) {
        Text(
            text = "$name ${if (pass) "✓" else "✕"}",
            color = if (pass) StatusGreen else StatusRed,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp),
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
fun SparklineChart(
    modifier: Modifier = Modifier,
    color: Color = ElectricCyan,
    points: List<Float> = listOf(10f, 15f, 12f, 18f, 25f, 22f, 30f, 38f, 35f, 48f)
) {
    val infiniteTransition = rememberInfiniteTransition(label = "chartPulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 3.dp.value,
        targetValue = 6.dp.value,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "dotPulse"
    )

    Canvas(modifier = modifier) {
        if (points.isEmpty()) return@Canvas
        val width = size.width
        val height = size.height
        val min = points.minOrNull() ?: 0f
        val max = points.maxOrNull() ?: 100f
        val range = if (max == min) 1f else (max - min)

        val path = Path()
        val fillPath = Path()
        val stepX = width / (points.size - 1)

        var lastX = 0f
        var lastY = 0f

        points.forEachIndexed { i, value ->
            val x = i * stepX
            val y = height - ((value - min) / range * height)
            if (i == 0) {
                path.moveTo(x, y)
                fillPath.moveTo(x, height)
                fillPath.lineTo(x, y)
            } else {
                path.lineTo(x, y)
                fillPath.lineTo(x, y)
            }
            if (i == points.lastIndex) {
                lastX = x
                lastY = y
                fillPath.lineTo(x, height)
                fillPath.close()
            }
        }

        // Draw area gradient fill
        drawPath(
            path = fillPath,
            brush = Brush.verticalGradient(
                colors = listOf(color.copy(alpha = 0.35f), Color.Transparent)
            )
        )

        // Draw line
        drawPath(
            path = path,
            color = color,
            style = Stroke(width = 2.dp.toPx())
        )

        // Draw live pulse glow at last point
        drawCircle(
            color = color.copy(alpha = 0.4f),
            radius = pulseScale * 2.dp.toPx(),
            center = androidx.compose.ui.geometry.Offset(lastX, lastY)
        )
        drawCircle(
            color = color,
            radius = 3.dp.toPx(),
            center = androidx.compose.ui.geometry.Offset(lastX, lastY)
        )
    }
}

@Composable
fun CyberHeroBanner(
    title: String,
    subtitle: String,
    badgeText: String,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .border(1.dp, BorderStroke(1.dp, Brush.horizontalGradient(listOf(StatusGreen.copy(alpha = 0.6f), ElectricCyan.copy(alpha = 0.6f)))).brush, RoundedCornerShape(12.dp)),
        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(110.dp)
        ) {
            Image(
                painter = painterResource(id = R.drawable.img_cyber_banner_1786547585581),
                contentDescription = "Cyber Quant Banner",
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize()
            )

            // Dark overlay gradient for contrast
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.horizontalGradient(
                            colors = listOf(
                                Color(0xFF03070A).copy(alpha = 0.92f),
                                Color(0xFF07121C).copy(alpha = 0.70f),
                                Color(0xFF03070A).copy(alpha = 0.88f)
                            )
                        )
                    )
            )

            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        LivePulseIndicator(sizeDp = 8)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = badgeText,
                            color = StatusGreen,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = title,
                        color = TextPrimary,
                        fontSize = 17.sp,
                        fontWeight = FontWeight.ExtraBold
                    )
                    Text(
                        text = subtitle,
                        color = TextSecondary,
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                Surface(
                    color = ElectricCyan.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(1.dp, ElectricCyan.copy(alpha = 0.4f))
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.AutoGraph,
                            contentDescription = "Analytics",
                            tint = ElectricCyan,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "LIVE FEED",
                            color = ElectricCyan,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun PipelineTimeline(
    currentStage: PipelineStage,
    modifier: Modifier = Modifier
) {
    val stages = PipelineStage.values()
    val currentIndex = stages.indexOf(currentStage)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        stages.forEachIndexed { index, stage ->
            val isCompleted = index < currentIndex
            val isCurrent = index == currentIndex

            val circleColor = when {
                isCurrent -> ElectricCyan
                isCompleted -> StatusGreen
                else -> GraphiteBorder
            }

            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.weight(1f)
            ) {
                Box(
                    modifier = Modifier
                        .size(20.dp)
                        .background(
                            color = when {
                                isCurrent -> ElectricCyan.copy(alpha = 0.2f)
                                isCompleted -> StatusGreenBg
                                else -> GraphiteSurfaceVariant
                            },
                            shape = CircleShape
                        )
                        .border(1.5.dp, circleColor, CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    if (isCompleted) {
                        Text(text = "✓", color = StatusGreen, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    } else if (isCurrent) {
                        Box(modifier = Modifier.size(6.dp).background(ElectricCyan, CircleShape))
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = stage.name.take(3),
                    color = if (isCurrent) ElectricCyan else if (isCompleted) TextPrimary else TextMuted,
                    fontSize = 9.sp,
                    fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal,
                    fontFamily = FontFamily.Monospace
                )
            }
        }
    }
}
