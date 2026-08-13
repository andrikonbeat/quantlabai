package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.SwapHoriz
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.StrategyStatus
import com.example.ui.QuantLabViewModel
import com.example.ui.components.StatusBadge
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReplacementEngineScreen(
    viewModel: QuantLabViewModel,
    onBackClick: () -> Unit
) {
    val strategies by viewModel.strategies.collectAsState()

    val degradedStrategies = strategies.filter { it.status == StrategyStatus.DEGRADED }
    val replacementReadyStrategies = strategies.filter { it.status == StrategyStatus.REPLACEMENT_READY || it.status == StrategyStatus.CANDIDATE }

    var selectedDegradedId by remember { mutableStateOf(degradedStrategies.firstOrNull()?.id ?: "") }
    var showConfirmModal by remember { mutableStateOf(false) }
    var selectedCandidateId by remember { mutableStateOf("") }

    if (showConfirmModal && selectedCandidateId.isNotEmpty()) {
        val cand = replacementReadyStrategies.find { it.id == selectedCandidateId }
        val deg = degradedStrategies.find { it.id == selectedDegradedId }

        AlertDialog(
            onDismissRequest = { showConfirmModal = false },
            title = { Text("Confirm Strategy Replacement", color = TextPrimary, fontWeight = FontWeight.Bold) },
            text = {
                Text(
                    "You are about to decommission degraded live strategy ${deg?.codeNumber} (${deg?.asset}) and deploy replacement candidate ${cand?.codeNumber} (Sharpe ${cand?.sharpeRatio}, Max DD ${cand?.maxDrawdownPct}%).\n\nHuman approval is enforced by Autonomy Policy.",
                    color = TextSecondary
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.replaceStrategy(degradedId = selectedDegradedId, candidateId = selectedCandidateId)
                        showConfirmModal = false
                        onBackClick()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = StatusGreen, contentColor = Color.White)
                ) {
                    Text("APPROVE REPLACEMENT", fontWeight = FontWeight.Bold)
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
                    Text(
                        text = "REPLACEMENT ENGINE",
                        color = TextPrimary,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
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
                .testTag("replacement_engine_screen"),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceAround
                    ) {
                        StatCell(title = "Live Strategies", value = "9", color = StatusGreen)
                        StatCell(title = "Degrading", value = "${degradedStrategies.size}", color = StatusRed)
                        StatCell(title = "Replacement Ready", value = "${replacementReadyStrategies.size}", color = ElectricCyan)
                    }
                }
            }

            // Degrading strategy warning
            item {
                Text(
                    text = "DEGRADING LIVE STRATEGIES",
                    color = TextSecondary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
            }

            if (degradedStrategies.isEmpty()) {
                item {
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                    ) {
                        Text(
                            text = "No strategies are currently experiencing alpha degradation.",
                            color = StatusGreen,
                            modifier = Modifier.padding(16.dp)
                        )
                    }
                }
            } else {
                items(degradedStrategies.size) { idx ->
                    val deg = degradedStrategies[idx]
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.5.dp, StatusRed, RoundedCornerShape(12.dp)),
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
                                    Icon(Icons.Default.Warning, contentDescription = "Degraded", tint = StatusRed, modifier = Modifier.size(18.dp))
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        "${deg.codeNumber} (${deg.asset} ${deg.timeframe})",
                                        color = TextPrimary,
                                        fontWeight = FontWeight.Bold,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                                Spacer(modifier = Modifier.width(8.dp))
                                StatusBadge(text = "DEGRADED", statusColor = StatusRed, bgColor = StatusRedBg)
                            }

                            Spacer(modifier = Modifier.height(8.dp))
                            Text("Drawdown: ${deg.maxDrawdownPct}% | Sharpe: ${deg.sharpeRatio} | Profit Factor: ${deg.profitFactor}", color = TextSecondary, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(deg.rejectionReason ?: "Alpha decay detected.", color = StatusRed, fontSize = 12.sp)
                        }
                    }
                }
            }

            // Ready Replacement Candidates
            item {
                Text(
                    text = "REPLACEMENT CANDIDATES READY FOR DEPLOYMENT",
                    color = TextSecondary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
            }

            items(replacementReadyStrategies.size) { idx ->
                val cand = replacementReadyStrategies[idx]
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, ElectricCyan, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("${cand.codeNumber} (${cand.asset} ${cand.timeframe})", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                            StatusBadge(text = "READY", statusColor = StatusGreen, bgColor = StatusGreenBg)
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Net Profit: ${cand.netProfit}", color = StatusGreen, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                            Text("Sharpe: ${cand.sharpeRatio}", color = ElectricCyan, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                            Text("Max DD: ${cand.maxDrawdownPct}%", color = TextSecondary, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                        }

                        Spacer(modifier = Modifier.height(14.dp))
                        Button(
                            onClick = {
                                selectedCandidateId = cand.id
                                showConfirmModal = true
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = Color.White),
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(8.dp),
                            enabled = degradedStrategies.isNotEmpty()
                        ) {
                            Icon(Icons.Default.SwapHoriz, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("REVIEW & REPLACE DEGRADED STRATEGY", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            item { Spacer(modifier = Modifier.height(40.dp)) }
        }
    }
}

@Composable
private fun StatCell(title: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(title, color = TextMuted, fontSize = 11.sp)
        Text(value, color = color, fontSize = 18.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
    }
}
