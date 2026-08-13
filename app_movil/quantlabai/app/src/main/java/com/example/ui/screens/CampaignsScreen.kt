package com.example.ui.screens

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
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
import com.example.data.model.CampaignStatus
import com.example.data.model.UiState
import com.example.ui.QuantLabViewModel
import com.example.ui.components.CampaignCard
import com.example.ui.theme.*

@Composable
fun CampaignsScreen(
    viewModel: QuantLabViewModel,
    onNavigateToCampaignDetail: (String) -> Unit,
    onNavigateToNewCampaign: () -> Unit
) {
    val campaignsUiState by viewModel.campaignsUiState.collectAsState()
    val campaigns = (campaignsUiState as? UiState.Success)?.data ?: emptyList()
    var selectedFilter by remember { mutableStateOf<CampaignStatus?>(null) }
    var searchQuery by remember { mutableStateOf("") }

    val filteredCampaigns = campaigns.filter { campaign ->
        (selectedFilter == null || campaign.status == selectedFilter) &&
                (searchQuery.isBlank() || campaign.name.contains(searchQuery, ignoreCase = true) || campaign.asset.contains(searchQuery, ignoreCase = true))
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .padding(horizontal = 16.dp)
            .testTag("campaigns_screen")
    ) {
        Spacer(modifier = Modifier.height(16.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "CAMPAIGNS",
                color = TextPrimary,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace
            )

            Button(
                onClick = onNavigateToNewCampaign,
                colors = ButtonDefaults.buttonColors(containerColor = StatusGreen, contentColor = androidx.compose.ui.graphics.Color.Black),
                shape = RoundedCornerShape(2.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, StatusGreen)
            ) {
                Text("+ NEW CAMPAIGN", fontWeight = FontWeight.Bold, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Search Bar
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            placeholder = { Text("Search by asset, timeframe, name...", color = TextMuted) },
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

        // Filter chips
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            item {
                FilterChip(
                    selected = selectedFilter == null,
                    onClick = { selectedFilter = null },
                    label = { Text("ALL (${campaigns.size})") },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ElectricCyan,
                        selectedLabelColor = androidx.compose.ui.graphics.Color.White,
                        containerColor = GraphiteCard,
                        labelColor = TextSecondary
                    )
                )
            }
            items(CampaignStatus.values()) { status ->
                val count = campaigns.count { it.status == status }
                FilterChip(
                    selected = selectedFilter == status,
                    onClick = { selectedFilter = if (selectedFilter == status) null else status },
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

        when (val campaignsState = campaignsUiState) {
            is UiState.Success -> {
                if (campaignsState.data.isEmpty()) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.TopCenter
                    ) {
                        CampaignsEmptyCard()
                    }
                } else {
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                        modifier = Modifier
                            .fillMaxSize()
                            .testTag("campaigns_list")
                    ) {
                        items(filteredCampaigns) { campaign ->
                            CampaignCard(
                                campaign = campaign,
                                onClick = { onNavigateToCampaignDetail(campaign.id) }
                            )
                        }
                        item { Spacer(modifier = Modifier.height(80.dp)) }
                    }
                }
            }

            is UiState.Error -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.TopCenter
                ) {
                    CampaignsErrorCard(
                        message = campaignsState.message,
                        onRetry = { viewModel.refreshCampaigns() }
                    )
                }
            }

            UiState.Loading -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.TopCenter
                ) {
                    CampaignsLoadingCard()
                }
            }
        }
    }
}

@Composable
private fun CampaignsLoadingCard() {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp))
            .testTag("campaigns_loading"),
        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "LOADING CAMPAIGNS...",
                color = TextSecondary,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(10.dp))
            LinearProgressIndicator(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(4.dp),
                color = ElectricCyan,
                trackColor = GraphiteSurfaceVariant
            )
        }
    }
}

@Composable
private fun CampaignsErrorCard(message: String, onRetry: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp))
            .testTag("campaigns_error"),
        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = "Connection error",
                    tint = StatusAmber,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "CONNECTION ERROR",
                    color = StatusAmber,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
            }
            if (message.isNotBlank()) {
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = message,
                    color = TextSecondary,
                    fontSize = 12.sp
                )
            }
            Spacer(modifier = Modifier.height(10.dp))
            Button(
                onClick = onRetry,
                modifier = Modifier.testTag("campaigns_retry"),
                colors = ButtonDefaults.buttonColors(containerColor = StatusAmber, contentColor = androidx.compose.ui.graphics.Color.Black),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text("RETRY", fontSize = 12.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
            }
        }
    }
}

@Composable
private fun CampaignsEmptyCard() {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp))
            .testTag("campaigns_empty"),
        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "NO CAMPAIGNS FOUND",
                color = TextMuted,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = "Create a new campaign to start generating strategies.",
                color = TextSecondary,
                fontSize = 12.sp
            )
        }
    }
}
