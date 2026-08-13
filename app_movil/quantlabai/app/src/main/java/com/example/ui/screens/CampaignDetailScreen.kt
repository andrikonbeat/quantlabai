package com.example.ui.screens

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import com.example.data.model.CampaignStatus
import com.example.data.model.ChatContextType
import com.example.ui.QuantLabViewModel
import com.example.ui.components.AgentCard
import com.example.ui.components.PipelineTimeline
import com.example.ui.components.StatusBadge
import com.example.ui.components.StrategyCard
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CampaignDetailScreen(
    campaignId: String,
    viewModel: QuantLabViewModel,
    onBackClick: () -> Unit,
    onNavigateToAgent: (String) -> Unit,
    onNavigateToStrategy: (String) -> Unit,
    onNavigateToChat: (ChatContextType, String) -> Unit
) {
    val campaigns by viewModel.campaigns.collectAsState()
    val agents by viewModel.agents.collectAsState()
    val strategies by viewModel.strategies.collectAsState()

    val campaign = campaigns.find { it.id == campaignId } ?: campaigns.first()
    val campaignAgents = agents.filter { it.campaignName.contains(campaign.asset) || it.campaignName == campaign.name }
    val campaignStrategies = strategies.filter { it.campaignId == campaign.id }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = campaign.name,
                            color = TextPrimary,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "${campaign.asset} ${campaign.timeframe} · ${campaign.id}",
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
                .testTag("campaign_detail_screen"),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Pipeline Stage
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
                                text = "RESEARCH PIPELINE",
                                color = TextSecondary,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                            StatusBadge(
                                text = campaign.status.name,
                                statusColor = StatusBlue,
                                bgColor = StatusBlueBg
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        PipelineTimeline(currentStage = campaign.currentStage)
                    }
                }
            }

            // Objective & Hypothesis Card
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "OBJECTIVE",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Text(
                            text = campaign.objective,
                            color = TextPrimary,
                            fontSize = 14.sp
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        Text(
                            text = "HYPOTHESIS",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Text(
                            text = campaign.hypothesis,
                            color = ElectricCyan,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }

            // Control Actions
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Button(
                        onClick = {
                            val newStatus = if (campaign.status == CampaignStatus.ACTIVE) CampaignStatus.PAUSED else CampaignStatus.ACTIVE
                            viewModel.updateCampaignStatus(campaign.id, newStatus)
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (campaign.status == CampaignStatus.ACTIVE) StatusAmber else StatusGreen,
                            contentColor = Color.Black
                        ),
                        modifier = Modifier.weight(1f),
                        contentPadding = PaddingValues(horizontal = 4.dp, vertical = 6.dp),
                        shape = RoundedCornerShape(2.dp)
                    ) {
                        Icon(
                            imageVector = if (campaign.status == CampaignStatus.ACTIVE) Icons.Default.Pause else Icons.Default.PlayArrow,
                            contentDescription = null,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = if (campaign.status == CampaignStatus.ACTIVE) "PAUSE" else "RESUME",
                            fontWeight = FontWeight.Bold,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1,
                            softWrap = false
                        )
                    }

                    Button(
                        onClick = { onNavigateToChat(ChatContextType.CAMPAIGN, campaign.name) },
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
                }
            }

            // Associated Active Agents
            item {
                Text(
                    text = "ACTIVE AGENTS (${campaignAgents.size})",
                    color = TextSecondary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
            }

            items(campaignAgents) { agent ->
                AgentCard(
                    agent = agent,
                    onDetailClick = { onNavigateToAgent(agent.id) }
                )
            }

            // Generated Strategies
            item {
                Text(
                    text = "STRATEGY CANDIDATES (${campaignStrategies.size})",
                    color = TextSecondary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
            }

            items(campaignStrategies) { strategy ->
                StrategyCard(
                    strategy = strategy,
                    onDetailClick = { onNavigateToStrategy(strategy.id) }
                )
            }

            item { Spacer(modifier = Modifier.height(40.dp)) }
        }
    }
}
