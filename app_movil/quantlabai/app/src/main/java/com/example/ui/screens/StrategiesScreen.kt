package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.StrategyStatus
import com.example.ui.QuantLabViewModel
import com.example.ui.components.CyberHeroBanner
import com.example.ui.components.StrategyCard
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StrategiesScreen(
    viewModel: QuantLabViewModel,
    onNavigateToStrategyDetail: (String) -> Unit,
    onBackClick: () -> Unit
) {
    val strategies by viewModel.strategies.collectAsState()
    var searchQuery by remember { mutableStateOf("") }
    var selectedStatusFilter by remember { mutableStateOf<StrategyStatus?>(null) }

    val filteredStrategies = strategies.filter { strat ->
        (selectedStatusFilter == null || strat.status == selectedStatusFilter) &&
                (searchQuery.isBlank() || strat.codeNumber.contains(searchQuery, ignoreCase = true) || strat.asset.contains(searchQuery, ignoreCase = true) || strat.id.contains(searchQuery, ignoreCase = true))
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "STRATEGY LABORATORY",
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp)
                .testTag("strategies_screen")
        ) {
            CyberHeroBanner(
                title = "Quantitative Strategy Vault",
                subtitle = "Algorithmic Models, Walk-Forward & Monte Carlo Filters",
                badgeText = "VAULT: ${strategies.size} MODELS"
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Search Input
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                placeholder = { Text("Filter by #8421, EURUSD, candidate...", color = TextMuted) },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = "Search", tint = TextSecondary) },
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, GraphiteBorder, RoundedCornerShape(8.dp)),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = GraphiteCard,
                    unfocusedContainerColor = GraphiteCard,
                    focusedBorderColor = ElectricCyan,
                    unfocusedBorderColor = GraphiteBorder,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary
                ),
                singleLine = true
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Status filter chips
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                item {
                    FilterChip(
                        selected = selectedStatusFilter == null,
                        onClick = { selectedStatusFilter = null },
                        label = { Text("ALL (${strategies.size})") },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = ElectricCyan,
                            selectedLabelColor = androidx.compose.ui.graphics.Color.White,
                            containerColor = GraphiteCard,
                            labelColor = TextSecondary
                        )
                    )
                }
                items(StrategyStatus.values()) { status ->
                    val count = strategies.count { it.status == status }
                    FilterChip(
                        selected = selectedStatusFilter == status,
                        onClick = { selectedStatusFilter = if (selectedStatusFilter == status) null else status },
                        label = { Text("${status.name} ($count)") },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = ElectricCyan,
                            selectedLabelColor = androidx.compose.ui.graphics.Color.White,
                            containerColor = GraphiteCard,
                            labelColor = TextSecondary
                        )
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(12.dp),
                modifier = Modifier.fillMaxSize()
            ) {
                items(filteredStrategies) { strategy ->
                    StrategyCard(
                        strategy = strategy,
                        onDetailClick = { onNavigateToStrategyDetail(strategy.id) }
                    )
                }
                item { Spacer(modifier = Modifier.height(40.dp)) }
            }
        }
    }
}
