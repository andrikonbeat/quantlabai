package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.StrategyStatus
import com.example.ui.QuantLabViewModel
import com.example.ui.components.SparklineChart
import com.example.ui.components.StatusBadge
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StrategyDetailScreen(
    strategyId: String,
    viewModel: QuantLabViewModel,
    onBackClick: () -> Unit
) {
    val strategies by viewModel.strategies.collectAsState()
    val approvals by viewModel.approvals.collectAsState()
    val strategy = strategies.find { it.id == strategyId } ?: strategies.first()
    val relatedApproval = approvals.find { it.strategyId == strategy.id }

    var showConfirmModal by remember { mutableStateOf(false) }

    if (showConfirmModal) {
        AlertDialog(
            onDismissRequest = { showConfirmModal = false },
            title = { Text("Approve Strategy Deployment", color = TextPrimary, fontWeight = FontWeight.Bold) },
            text = {
                Text(
                    "Are you sure you want to approve Strategy ${strategy.codeNumber} (${strategy.asset} ${strategy.timeframe}) for live portfolio allocation?\n\nThis action will initiate capital assignment.",
                    color = TextSecondary
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (relatedApproval != null) {
                            viewModel.approveItem(relatedApproval.id)
                        }
                        showConfirmModal = false
                        onBackClick()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = StatusGreen, contentColor = Color.White)
                ) {
                    Text("CONFIRM APPROVAL", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = { showConfirmModal = false },
                    border = BorderStroke(1.dp, GraphiteBorder)
                ) {
                    Text("CANCEL", color = TextPrimary)
                }
            },
            containerColor = GraphiteCard
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "STRATEGY ${strategy.codeNumber}",
                            color = TextPrimary,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Text(
                            text = "${strategy.asset} · ${strategy.timeframe} · Score ${strategy.score}",
                            color = ElectricCyan,
                            fontSize = 12.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = TextPrimary)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = GraphiteBackground)
            )
        },
        containerColor = GraphiteBackground
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp)
                .testTag("strategy_detail_screen"),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Header card
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "OVERALL STATUS",
                                color = TextMuted,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                            StatusBadge(
                                text = strategy.status.name,
                                statusColor = if (strategy.status == StrategyStatus.LIVE) StatusGreen else ElectricCyan,
                                bgColor = if (strategy.status == StrategyStatus.LIVE) StatusGreenBg else CyanGlow
                            )
                        }

                        if (strategy.rejectionReason != null) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "Note: ${strategy.rejectionReason}",
                                color = StatusRed,
                                fontSize = 12.sp
                            )
                        }

                        Spacer(modifier = Modifier.height(14.dp))
                        Text(
                            text = "EQUITY CURVE SIMULATION",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        SparklineChart(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(60.dp),
                            color = StatusGreen
                        )
                    }
                }
            }

            // Performance Metrics Grid
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "PERFORMANCE METRICS",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Spacer(modifier = Modifier.height(12.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            DetailMetric(label = "Net Profit", value = strategy.netProfit, color = StatusGreen)
                            DetailMetric(label = "Profit Factor", value = String.format("%.2f", strategy.profitFactor))
                            DetailMetric(label = "Max Drawdown", value = "${strategy.maxDrawdownPct}%", color = StatusRed)
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            DetailMetric(label = "Sharpe Ratio", value = String.format("%.2f", strategy.sharpeRatio), color = ElectricCyan)
                            DetailMetric(label = "Recovery Factor", value = String.format("%.2f", strategy.recoveryFactor))
                            DetailMetric(label = "Quality Score", value = "${strategy.score}/100", color = StatusAmber)
                        }
                    }
                }
            }

            // Robustness Matrix
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "ROBUSTNESS TESTING MATRIX",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Spacer(modifier = Modifier.height(12.dp))

                        RobustnessRow(name = "Walk Forward Analysis", pass = strategy.walkForwardPass)
                        RobustnessRow(name = "Monte Carlo Permutation (1,000 runs)", pass = strategy.monteCarloPass)
                        RobustnessRow(name = "Parameter Sensitivity (+/- 30%)", pass = strategy.parameterStabilityPass)
                        RobustnessRow(name = "Market Regime Stress Test", pass = strategy.marketRegimePass)
                    }
                }
            }

            // Portfolio Fit
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "PORTFOLIO FIT & CORRELATION",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Spacer(modifier = Modifier.height(10.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Correlation vs Active Portfolio:", color = TextSecondary, fontSize = 13.sp)
                            Text(strategy.correlationStatus, color = StatusGreen, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 13.sp)
                        }
                        Spacer(modifier = Modifier.height(6.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Sector Concentration Risk:", color = TextSecondary, fontSize = 13.sp)
                            Text(strategy.exposureStatus, color = StatusGreen, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 13.sp)
                        }
                    }
                }
            }

            // Decision Action Bar
            item {
                Column {
                    Text(
                        text = "HUMAN DECISION WORKFLOW",
                        color = TextMuted,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(bottom = 8.dp)
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = { showConfirmModal = true },
                            colors = ButtonDefaults.buttonColors(containerColor = StatusGreen, contentColor = Color.White),
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            enabled = strategy.status != StrategyStatus.REJECTED
                        ) {
                            Text("APPROVE", fontWeight = FontWeight.Bold)
                        }

                        OutlinedButton(
                            onClick = {
                                if (relatedApproval != null) {
                                    viewModel.rejectItem(relatedApproval.id)
                                }
                                onBackClick()
                            },
                            border = BorderStroke(1.dp, StatusRed),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = StatusRed),
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("REJECT", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            item { Spacer(modifier = Modifier.height(40.dp)) }
        }
    }
}

@Composable
private fun DetailMetric(label: String, value: String, color: Color = TextPrimary) {
    Column {
        Text(text = label, color = TextMuted, fontSize = 11.sp)
        Text(
            text = value,
            color = color,
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun RobustnessRow(name: String, pass: Boolean) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = name, color = TextPrimary, fontSize = 13.sp)
        StatusBadge(
            text = if (pass) "PASS" else "FAIL",
            statusColor = if (pass) StatusGreen else StatusRed,
            bgColor = if (pass) StatusGreenBg else StatusRedBg,
            showDot = false
        )
    }
}
