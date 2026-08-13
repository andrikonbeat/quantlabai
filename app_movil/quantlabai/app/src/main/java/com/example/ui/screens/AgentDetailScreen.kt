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
import com.example.data.model.AgentLogEntry
import com.example.data.model.AgentStatus
import com.example.data.model.ChatContextType
import com.example.data.model.LogLevel
import com.example.ui.QuantLabViewModel
import com.example.ui.components.StatusBadge
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentDetailScreen(
    agentId: String,
    viewModel: QuantLabViewModel,
    onBackClick: () -> Unit,
    onNavigateToChat: (ChatContextType, String) -> Unit,
    onNavigateToLogs: () -> Unit
) {
    val agents by viewModel.agents.collectAsState()
    val agent = agents.find { it.id == agentId } ?: agents.first()
    var selectedFilter by remember { mutableStateOf<LogLevel?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(agent.name, color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold)
                        Text(agent.role, color = ElectricCyan, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
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
                .testTag("agent_detail_screen"),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
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
                            StatusBadge(
                                text = agent.status.name,
                                statusColor = if (agent.status == AgentStatus.RUNNING) StatusBlue else StatusAmber,
                                bgColor = if (agent.status == AgentStatus.RUNNING) StatusBlueBg else StatusAmberBg
                            )
                            Text(
                                text = "Runtime: ${agent.runtime}",
                                color = TextMuted,
                                fontSize = 12.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Text(
                            text = "CURRENT TASK",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Text(
                            text = agent.currentTask,
                            color = TextPrimary,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )

                        Spacer(modifier = Modifier.height(14.dp))

                        // Progress
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Execution Progress", color = TextSecondary, fontSize = 12.sp)
                            Text("${agent.progressPct}%", color = ElectricCyan, fontSize = 12.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        }
                        Spacer(modifier = Modifier.height(6.dp))
                        LinearProgressIndicator(
                            progress = { agent.progressPct / 100f },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(6.dp),
                            color = ElectricCyan,
                            trackColor = GraphiteSurfaceVariant
                        )

                        Spacer(modifier = Modifier.height(14.dp))

                        Text(
                            text = "CURRENT INSTRUCTION",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Text(
                            text = "\"${agent.currentInstruction}\"",
                            color = ElectricCyan,
                            fontSize = 13.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }

            // Metrics row
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
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Generated", color = TextMuted, fontSize = 11.sp)
                            Text("${agent.generatedCount}", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        }
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Passed Filters", color = TextMuted, fontSize = 11.sp)
                            Text("${agent.passedCount}", color = StatusGreen, fontSize = 18.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        }
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Campaign", color = TextMuted, fontSize = 11.sp)
                            Text(agent.campaignName, color = ElectricCyan, fontSize = 14.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        }
                    }
                }
            }

            // Action Buttons (TUI Single-Line Format)
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Button(
                        onClick = { onNavigateToChat(ChatContextType.AGENT, agent.name) },
                        colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = Color.Black),
                        modifier = Modifier.weight(1f),
                        contentPadding = PaddingValues(horizontal = 4.dp, vertical = 6.dp),
                        shape = RoundedCornerShape(2.dp)
                    ) {
                        Icon(Icons.AutoMirrored.Filled.Chat, contentDescription = null, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "CHAT",
                            fontWeight = FontWeight.Bold,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1,
                            softWrap = false
                        )
                    }

                    Button(
                        onClick = { viewModel.toggleAgentStatus(agent.id) },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (agent.status == AgentStatus.RUNNING) StatusAmber else StatusGreen,
                            contentColor = Color.Black
                        ),
                        modifier = Modifier.weight(1f),
                        contentPadding = PaddingValues(horizontal = 4.dp, vertical = 6.dp),
                        shape = RoundedCornerShape(2.dp)
                    ) {
                        Icon(
                            imageVector = if (agent.status == AgentStatus.RUNNING) Icons.Default.Pause else Icons.Default.PlayArrow,
                            contentDescription = null,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = if (agent.status == AgentStatus.RUNNING) "PAUSE" else "RESUME",
                            fontWeight = FontWeight.Bold,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1,
                            softWrap = false
                        )
                    }

                    OutlinedButton(
                        onClick = onNavigateToLogs,
                        border = BorderStroke(1.dp, ElectricCyan.copy(alpha = 0.5f)),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = TextPrimary),
                        modifier = Modifier.weight(1f),
                        contentPadding = PaddingValues(horizontal = 4.dp, vertical = 6.dp),
                        shape = RoundedCornerShape(2.dp)
                    ) {
                        Icon(Icons.Default.Terminal, contentDescription = null, modifier = Modifier.size(14.dp), tint = ElectricCyan)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "CONSOLE",
                            fontWeight = FontWeight.Bold,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1,
                            softWrap = false
                        )
                    }
                }
            }

            // Sub-Agent Live Console & Terminal Logs
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF030507))
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
                                        .size(8.dp)
                                        .background(StatusGreen, CircleShape)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = "SUB-AGENT EXECUTION LOGS",
                                    color = TextPrimary,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold,
                                    fontFamily = FontFamily.Monospace
                                )
                            }
                            Text(
                                text = "${agent.logs.size} EVENTS",
                                color = TextMuted,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        // Filter Chips
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            val filters = listOf<LogLevel?>(null, LogLevel.INFO, LogLevel.EXEC, LogLevel.WARN, LogLevel.SUCCESS)
                            filters.forEach { level ->
                                val isSelected = selectedFilter == level
                                val label = level?.name ?: "ALL"
                                Surface(
                                    color = if (isSelected) ElectricCyan.copy(alpha = 0.2f) else GraphiteSurface,
                                    border = BorderStroke(1.dp, if (isSelected) ElectricCyan else GraphiteBorder),
                                    shape = RoundedCornerShape(4.dp),
                                    modifier = Modifier.clickable { selectedFilter = level }
                                ) {
                                    Text(
                                        text = label,
                                        color = if (isSelected) ElectricCyan else TextMuted,
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        fontFamily = FontFamily.Monospace,
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                    )
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(14.dp))
                        HorizontalDivider(color = GraphiteBorder.copy(alpha = 0.5f))
                        Spacer(modifier = Modifier.height(14.dp))

                        val filteredLogs = if (selectedFilter == null) {
                            agent.logs
                        } else {
                            agent.logs.filter { it.level == selectedFilter }
                        }

                        if (filteredLogs.isEmpty()) {
                            Text(
                                text = "No log entries found for this filter.",
                                color = TextMuted,
                                fontSize = 12.sp,
                                fontFamily = FontFamily.Monospace,
                                modifier = Modifier.padding(vertical = 12.dp)
                            )
                        } else {
                            filteredLogs.forEach { log ->
                                AgentLogRow(log = log)
                                Spacer(modifier = Modifier.height(10.dp))
                            }
                        }
                    }
                }
            }

            item { Spacer(modifier = Modifier.height(40.dp)) }
        }
    }
}

@Composable
private fun AgentLogRow(log: AgentLogEntry) {
    val (levelColor, levelBg) = when (log.level) {
        LogLevel.INFO -> StatusBlue to StatusBlueBg
        LogLevel.EXEC -> ElectricCyan to CyanGlow
        LogLevel.WARN -> StatusAmber to StatusAmberBg
        LogLevel.ERROR -> StatusRed to StatusRedBg
        LogLevel.SUCCESS -> StatusGreen to StatusGreenBg
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(GraphiteSurface.copy(alpha = 0.5f), RoundedCornerShape(6.dp))
            .border(1.dp, GraphiteBorder.copy(alpha = 0.5f), RoundedCornerShape(6.dp))
            .padding(10.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    color = levelBg,
                    shape = RoundedCornerShape(3.dp)
                ) {
                    Text(
                        text = log.level.name,
                        color = levelColor,
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
                log.stepName?.let { step ->
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = step,
                        color = TextSecondary,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
            Text(
                text = log.timestamp,
                color = TextMuted,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )
        }

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = log.message,
            color = TextPrimary,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace
        )

        log.details?.let { details ->
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "└─ $details",
                color = TextMuted,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}
