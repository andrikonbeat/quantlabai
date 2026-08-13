package com.example.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.QuantLabViewModel
import com.example.ui.components.AgentCard
import com.example.ui.components.CyberHeroBanner
import com.example.ui.theme.GraphiteBackground
import com.example.ui.theme.TextPrimary

@Composable
fun AgentsScreen(
    viewModel: QuantLabViewModel,
    onNavigateToAgentDetail: (String) -> Unit
) {
    val agents by viewModel.agents.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .padding(horizontal = 16.dp)
            .testTag("agents_screen")
    ) {
        Spacer(modifier = Modifier.height(16.dp))

        CyberHeroBanner(
            title = "Autonomous Agent Fleet",
            subtitle = "Specialized AI Workers: Generator, Validator, Refiner, Deployer",
            badgeText = "FLEET: ${agents.size} WORKERS ACTIVE"
        )

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "AUTONOMOUS AGENTS (${agents.size})",
            color = TextPrimary,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(16.dp))

        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.fillMaxSize()
        ) {
            items(agents) { agent ->
                AgentCard(
                    agent = agent,
                    onDetailClick = { onNavigateToAgentDetail(agent.id) }
                )
            }
            item { Spacer(modifier = Modifier.height(80.dp)) }
        }
    }
}
