package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.QuantLabViewModel
import com.example.ui.components.CyberHeroBanner
import com.example.ui.components.LivePulseIndicator
import com.example.ui.components.StatusBadge
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InfrastructureScreen(
    viewModel: QuantLabViewModel,
    onBackClick: () -> Unit
) {
    val systemHealth by viewModel.systemHealth.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "INFRASTRUCTURE HEALTH",
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
                .testTag("infrastructure_screen"),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                CyberHeroBanner(
                    title = "Cluster Topology & Telemetry",
                    subtitle = "Real-time Node Health, Memory & CPU Workload",
                    badgeText = "HEALTH: 100% OPERATIONAL"
                )
            }

            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("RESOURCE UTILIZATION", color = TextMuted, fontSize = 11.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        Spacer(modifier = Modifier.height(14.dp))

                        ResourceBar(label = "CPU Cluster Usage", pct = systemHealth.cpuUsagePct)
                        Spacer(modifier = Modifier.height(10.dp))
                        ResourceBar(label = "RAM Memory Allocation", pct = systemHealth.ramUsagePct)
                        Spacer(modifier = Modifier.height(10.dp))
                        ResourceBar(label = "High-Speed SSD Storage", pct = systemHealth.storageUsagePct)
                    }
                }
            }

            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("CORE SERVICE NODES", color = TextMuted, fontSize = 11.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        Spacer(modifier = Modifier.height(12.dp))

                        NodeRow("OpenCode Runtime Environment", "ONLINE", StatusGreen)
                        NodeRow("Master Agent Orchestrator", "RUNNING", StatusGreen)
                        NodeRow("StrategyQuant X Generation Cluster", "ONLINE", StatusGreen)
                        NodeRow("Dukascopy Tick Data Pipeline", "ONLINE", StatusGreen)
                        NodeRow("Room SQLite Data Vault", "ONLINE", StatusGreen)
                        NodeRow("REST API Gateway", "HEALTHY (18ms)", StatusGreen)
                    }
                }
            }

            item { Spacer(modifier = Modifier.height(40.dp)) }
        }
    }
}

@Composable
private fun ResourceBar(label: String, pct: Int) {
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(label, color = TextPrimary, fontSize = 13.sp)
            Text("$pct%", color = ElectricCyan, fontSize = 13.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
        }
        Spacer(modifier = Modifier.height(6.dp))
        LinearProgressIndicator(
            progress = { pct / 100f },
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp),
            color = if (pct > 80) StatusRed else ElectricCyan,
            trackColor = GraphiteSurfaceVariant
        )
    }
}

@Composable
private fun NodeRow(name: String, status: String, color: androidx.compose.ui.graphics.Color) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            LivePulseIndicator(sizeDp = 6, color = color)
            Spacer(modifier = Modifier.width(8.dp))
            Text(name, color = TextPrimary, fontSize = 13.sp)
        }
        StatusBadge(text = status, statusColor = color, bgColor = StatusGreenBg)
    }
}
