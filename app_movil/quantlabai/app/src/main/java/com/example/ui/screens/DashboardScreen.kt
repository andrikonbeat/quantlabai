package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.*
import com.example.ui.QuantLabViewModel
import com.example.ui.components.*
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    viewModel: QuantLabViewModel,
    onNavigateToCampaign: (String) -> Unit,
    onNavigateToStrategy: (String) -> Unit,
    onNavigateToNewCampaign: () -> Unit,
    onNavigateToApprovals: () -> Unit
) {
    val approvals by viewModel.approvals.collectAsState()
    val activityEvents by viewModel.activityEvents.collectAsState()
    val strategies by viewModel.strategies.collectAsState()
    val systemHealthUiState by viewModel.systemHealthUiState.collectAsState()
    val campaignsUiState by viewModel.campaignsUiState.collectAsState()
    val statsUiState by viewModel.statsUiState.collectAsState()
    val lastRefreshed by viewModel.lastRefreshed.collectAsState()

    val pendingApproval = approvals.firstOrNull { it.status == ApprovalStatus.PENDING }
    val activeOrchestrator by viewModel.activeOrchestrator.collectAsState()

    Scaffold(
        containerColor = GraphiteBackground,
        contentWindowInsets = WindowInsets.statusBars
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            when (val health = systemHealthUiState) {
                is UiState.Loading -> {
                    item {
                        DashboardStateCard(tag = "dashboard_loading", isError = false)
                    }
                }

                is UiState.Error -> {
                    item {
                        DashboardStateCard(
                            tag = "dashboard_error",
                            retryTag = "dashboard_retry",
                            isError = true,
                            message = health.message,
                            onRetry = { viewModel.refreshData() }
                        )
                    }
                }

                is UiState.Success -> {
                    item { Spacer(modifier = Modifier.height(8.dp)) }

            // Cyber Hero Banner
            item {
                CyberHeroBanner(
                    title = "QuantLab Alpha Engine",
                    subtitle = "Automated Strategy Generation & Autonomous Pipeline",
                    badgeText = "SYSTEM ONLINE · $activeOrchestrator"
                )
            }

            // TUI Header Banner
            item {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(GraphiteSurface, RoundedCornerShape(8.dp))
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(8.dp))
                        .padding(12.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            LivePulseIndicator(sizeDp = 8)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "QuantLab AI",
                                color = TextPrimary,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                        }

                        Surface(
                            modifier = Modifier.clip(RoundedCornerShape(2.dp)),
                            color = GraphiteSurfaceVariant,
                            border = BorderStroke(1.dp, if (pendingApproval != null) StatusAmber else GraphiteBorder)
                        ) {
                            Box(
                                modifier = Modifier
                                    .clickable { onNavigateToApprovals() }
                                    .padding(horizontal = 8.dp, vertical = 4.dp)
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        imageVector = Icons.Default.Notifications,
                                        contentDescription = "Approvals",
                                        tint = if (pendingApproval != null) StatusAmber else TextSecondary,
                                        modifier = Modifier.size(14.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        text = if (pendingApproval != null) "[1 QUEUED]" else "[0 QUEUED]",
                                        color = if (pendingApproval != null) StatusAmber else TextSecondary,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = "❯ opencode --status ",
                                color = TextMuted,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace
                            )
                            Text(
                                text = "ACTIVE",
                                color = StatusGreen,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                        Text(
                            text = "SQX: LINKED · OP: elBoni",
                            color = TextSecondary,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }

                    if (lastRefreshed.isNotBlank()) {
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "LAST REFRESHED $lastRefreshed",
                            color = TextSecondary,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier.testTag("dashboard_last_refresh")
                        )
                    }
                }
            }

            // System Health
            item {
                HealthCard(systemHealth = health.data)
            }

            // Attention Required Section
            item {
                Column {
                    Text(
                        text = "ATTENTION REQUIRED",
                        color = TextSecondary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(bottom = 8.dp)
                    )

                    if (pendingApproval != null) {
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .border(1.5.dp, StatusAmber, RoundedCornerShape(12.dp)),
                            colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Row(
                                        modifier = Modifier.weight(1f),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.Warning,
                                            contentDescription = "Attention",
                                            tint = StatusAmber,
                                            modifier = Modifier.size(18.dp)
                                        )
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Text(
                                            text = pendingApproval.title,
                                            color = TextPrimary,
                                            fontSize = 15.sp,
                                            fontWeight = FontWeight.Bold,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                    }
                                    Spacer(modifier = Modifier.width(8.dp))
                                    StatusBadge(
                                        text = "HUMAN APPROVAL",
                                        statusColor = StatusAmber,
                                        bgColor = StatusAmberBg
                                    )
                                }

                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = pendingApproval.metricsSummary,
                                    color = ElectricCyan,
                                    fontSize = 12.sp,
                                    fontFamily = FontFamily.Monospace
                                )
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = pendingApproval.reason,
                                    color = TextSecondary,
                                    fontSize = 13.sp
                                )

                                Spacer(modifier = Modifier.height(14.dp))
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.End
                                ) {
                                    OutlinedButton(
                                        onClick = { onNavigateToStrategy(pendingApproval.strategyId) },
                                        border = BorderStroke(1.dp, GraphiteBorder),
                                        colors = ButtonDefaults.outlinedButtonColors(contentColor = TextPrimary),
                                        shape = RoundedCornerShape(8.dp)
                                    ) {
                                        Text("REVIEW", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                    }
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Button(
                                        onClick = { viewModel.approveItem(pendingApproval.id) },
                                        colors = ButtonDefaults.buttonColors(containerColor = StatusGreen, contentColor = Color.White),
                                        shape = RoundedCornerShape(8.dp)
                                    ) {
                                        Text("APPROVE", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                    }
                                }
                            }
                        }
                    } else {
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                            colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                        ) {
                            Row(
                                modifier = Modifier.padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.CheckCircle,
                                    contentDescription = "No action required",
                                    tint = StatusGreen,
                                    modifier = Modifier.size(22.dp)
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Column {
                                    Text(
                                        text = "No Action Required",
                                        color = TextPrimary,
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Text(
                                        text = "System is operating autonomously.",
                                        color = TextSecondary,
                                        fontSize = 12.sp
                                    )
                                }
                            }
                        }
                    }
                }
            }

            // Key Metrics
            item {
                Column {
                    Text(
                        text = "KEY METRICS",
                        color = TextSecondary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(bottom = 8.dp)
                    )

                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp))
                            .testTag("dashboard_content"),
                        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            val stats = (statsUiState as? UiState.Success)?.data
                            val generatedValue = stats?.let { String.format("%,d", it.totalTrades) } ?: "—"
                            val campaignsValue = stats?.totalCampaigns?.toString() ?: "—"
                            val pipelineValue = stats?.totalPipelineRuns?.toString() ?: "—"
                            val sharpeValue = stats?.let { String.format("%.2f", it.sharpeMean) } ?: "—"
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                MetricCell(title = "Generated", value = generatedValue, color = TextPrimary)
                                MetricCell(title = "Campaigns", value = campaignsValue, color = StatusBlue)
                                MetricCell(title = "Pipeline Runs", value = pipelineValue, color = StatusAmber)
                                MetricCell(title = "Total Sharpe", value = sharpeValue, color = StatusGreen)
                            }
                            Spacer(modifier = Modifier.height(14.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "30-Day Strategy Generation Velocity",
                                    color = TextMuted,
                                    fontSize = 11.sp
                                )
                                Spacer(modifier = Modifier.weight(1f))
                                SparklineChart(
                                    modifier = Modifier
                                        .width(120.dp)
                                        .height(24.dp)
                                )
                            }
                        }
                    }
                }
            }

            // Active Campaigns Section
            when (val campaignsState = campaignsUiState) {
                is UiState.Success -> {
                    val campaigns = campaignsState.data
                    item {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "ACTIVE CAMPAIGNS",
                                color = TextSecondary,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 1.sp,
                                fontFamily = FontFamily.Monospace
                            )

                            Text(
                                text = "${campaigns.size} RUNNING",
                                color = ElectricCyan,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    items(campaigns) { campaign ->
                        CampaignCard(
                            campaign = campaign,
                            onClick = { onNavigateToCampaign(campaign.id) }
                        )
                    }
                }

                is UiState.Error -> {
                    item {
                        DashboardStateCard(
                            tag = "dashboard_campaigns_error",
                            retryTag = "dashboard_campaigns_retry",
                            isError = true,
                            message = campaignsState.message,
                            onRetry = { viewModel.refreshCampaigns() }
                        )
                    }
                }

                UiState.Loading -> {
                    item {
                        DashboardStateCard(tag = "campaigns_loading", isError = false)
                    }
                }
            }

            // Recent Activity Section
            item {
                Column {
                    Text(
                        text = "RECENT ACTIVITY",
                        color = TextSecondary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(vertical = 8.dp)
                    )

                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            activityEvents.take(4).forEachIndexed { idx, event ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 6.dp),
                                    verticalAlignment = Alignment.Top
                                ) {
                                    Text(
                                        text = event.timestamp,
                                        color = TextMuted,
                                        fontSize = 11.sp,
                                        fontFamily = FontFamily.Monospace,
                                        modifier = Modifier.width(48.dp)
                                    )
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            text = event.source,
                                            color = ElectricCyan,
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold
                                        )
                                        Text(
                                            text = event.message,
                                            color = TextPrimary,
                                            fontSize = 13.sp
                                        )
                                    }
                                }
                                if (idx < 3) {
                                    HorizontalDivider(color = GraphiteBorder, thickness = 0.5.dp)
                                }
                            }
                        }
                    }
                }
            }

            item { Spacer(modifier = Modifier.height(80.dp)) }
                }
            }
        }
    }
}

@Composable
private fun MetricCell(title: String, value: String, color: Color) {
    Column {
        Text(text = title, color = TextMuted, fontSize = 11.sp)
        Text(
            text = value,
            color = color,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun DashboardStateCard(
    tag: String,
    retryTag: String = "",
    isError: Boolean = false,
    message: String = "",
    onRetry: () -> Unit = {}
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp))
            .testTag(tag),
        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (isError) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Connection error",
                        tint = StatusAmber,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                }
                Text(
                    text = if (isError) "CONNECTION ERROR" else "LOADING...",
                    color = if (isError) StatusAmber else TextSecondary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
                if (!isError) {
                    Spacer(modifier = Modifier.weight(1f))
                    LinearProgressIndicator(
                        modifier = Modifier
                            .width(64.dp)
                            .height(4.dp),
                        color = ElectricCyan,
                        trackColor = GraphiteSurfaceVariant
                    )
                }
            }

            if (isError && message.isNotBlank()) {
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = message,
                    color = TextSecondary,
                    fontSize = 12.sp
                )
            }

            if (isError) {
                Spacer(modifier = Modifier.height(10.dp))
                Button(
                    onClick = onRetry,
                    modifier = Modifier.testTag(retryTag),
                    colors = ButtonDefaults.buttonColors(containerColor = StatusAmber, contentColor = Color.Black),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("RETRY", fontSize = 12.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                }
            }
        }
    }
}
