package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
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
import com.example.ui.QuantLabViewModel
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NewCampaignWizardScreen(
    viewModel: QuantLabViewModel,
    onBackClick: () -> Unit,
    onCampaignCreated: () -> Unit
) {
    var currentStep by remember { mutableIntStateOf(1) }

    var campaignName by remember { mutableStateOf("AUDUSD H1 Volatility Expansion") }
    var objective by remember { mutableStateOf("Capture post-RBA rate decision volatility spikes.") }
    var hypothesis by remember { mutableStateOf("H-052: Donchian Channel breakout with ATR expansion filter.") }
    var selectedAsset by remember { mutableStateOf("AUDUSD") }
    var selectedTimeframe by remember { mutableStateOf("H1") }
    var maxDrawdownConstraint by remember { mutableStateOf("8.0") }
    var minSharpeConstraint by remember { mutableStateOf("1.8") }

    val assets = listOf("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSD", "BTCUSD")
    val timeframes = listOf("M15", "M30", "H1", "H4", "D1")

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "CREATE RESEARCH CAMPAIGN",
                            color = TextPrimary,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Text(
                            text = "Step $currentStep of 7",
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp)
                .testTag("new_campaign_wizard")
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            // Step Progress Bar
            LinearProgressIndicator(
                progress = { currentStep / 7f },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(6.dp),
                color = ElectricCyan,
                trackColor = GraphiteSurfaceVariant
            )

            Spacer(modifier = Modifier.height(16.dp))

            Card(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                colors = CardDefaults.cardColors(containerColor = GraphiteCard)
            ) {
                LazyColumn(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    item {
                        when (currentStep) {
                            1 -> {
                                Text("STEP 1: CAMPAIGN NAME & OBJECTIVE", color = ElectricCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
                                Spacer(modifier = Modifier.height(12.dp))
                                OutlinedTextField(
                                    value = campaignName,
                                    onValueChange = { campaignName = it },
                                    label = { Text("Campaign Name", color = TextSecondary) },
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary)
                                )
                                Spacer(modifier = Modifier.height(12.dp))
                                OutlinedTextField(
                                    value = objective,
                                    onValueChange = { objective = it },
                                    label = { Text("Research Objective", color = TextSecondary) },
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary)
                                )
                            }
                            2 -> {
                                Text("STEP 2: FORMULATE HYPOTHESIS", color = ElectricCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
                                Spacer(modifier = Modifier.height(12.dp))
                                OutlinedTextField(
                                    value = hypothesis,
                                    onValueChange = { hypothesis = it },
                                    label = { Text("Quantitative Hypothesis Statement", color = TextSecondary) },
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary)
                                )
                            }
                            3 -> {
                                Text("STEP 3: SELECT ASSET CLASS", color = ElectricCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
                                Spacer(modifier = Modifier.height(12.dp))
                                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    items(assets) { asset ->
                                        FilterChip(
                                            selected = selectedAsset == asset,
                                            onClick = { selectedAsset = asset },
                                            label = { Text(asset, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace) },
                                            colors = FilterChipDefaults.filterChipColors(
                                                selectedContainerColor = ElectricCyan,
                                                selectedLabelColor = Color.White,
                                                containerColor = GraphiteSurfaceVariant,
                                                labelColor = TextSecondary
                                            )
                                        )
                                    }
                                }
                            }
                            4 -> {
                                Text("STEP 4: TIMEFRAME SELECTION", color = ElectricCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
                                Spacer(modifier = Modifier.height(12.dp))
                                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    items(timeframes) { tf ->
                                        FilterChip(
                                            selected = selectedTimeframe == tf,
                                            onClick = { selectedTimeframe = tf },
                                            label = { Text(tf, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace) },
                                            colors = FilterChipDefaults.filterChipColors(
                                                selectedContainerColor = ElectricCyan,
                                                selectedLabelColor = Color.White,
                                                containerColor = GraphiteSurfaceVariant,
                                                labelColor = TextSecondary
                                            )
                                        )
                                    }
                                }
                            }
                            5 -> {
                                Text("STEP 5: RESEARCH SCOPE", color = ElectricCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
                                Spacer(modifier = Modifier.height(12.dp))
                                Text("✓ Macro Economic Indicators", color = StatusGreen, fontSize = 14.sp)
                                Text("✓ CFTC Commitments of Traders (COT)", color = StatusGreen, fontSize = 14.sp)
                                Text("✓ Dukascopy Tick Data Quality Check", color = StatusGreen, fontSize = 14.sp)
                            }
                            6 -> {
                                Text("STEP 6: GENERATION & VALIDATION CONSTRAINTS", color = ElectricCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
                                Spacer(modifier = Modifier.height(12.dp))
                                OutlinedTextField(
                                    value = maxDrawdownConstraint,
                                    onValueChange = { maxDrawdownConstraint = it },
                                    label = { Text("Maximum Allowed Drawdown (%)", color = TextSecondary) },
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary)
                                )
                                Spacer(modifier = Modifier.height(12.dp))
                                OutlinedTextField(
                                    value = minSharpeConstraint,
                                    onValueChange = { minSharpeConstraint = it },
                                    label = { Text("Minimum Sharpe Ratio", color = TextSecondary) },
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary)
                                )
                            }
                            7 -> {
                                Text("STEP 7: REVIEW & AUTONOMY CONFIRMATION", color = ElectricCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
                                Spacer(modifier = Modifier.height(12.dp))
                                Text("Name: $campaignName", color = TextPrimary, fontWeight = FontWeight.Bold)
                                Text("Asset: $selectedAsset $selectedTimeframe", color = ElectricCyan, fontFamily = FontFamily.Monospace)
                                Text("Objective: $objective", color = TextSecondary)
                                Text("Hypothesis: $hypothesis", color = TextSecondary)
                                Text("Constraints: Max DD < $maxDrawdownConstraint%, Sharpe > $minSharpeConstraint", color = StatusGreen, fontFamily = FontFamily.Monospace)
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                if (currentStep > 1) {
                    OutlinedButton(
                        onClick = { currentStep-- },
                        border = BorderStroke(1.dp, GraphiteBorder)
                    ) {
                        Text("BACK", color = TextPrimary)
                    }
                } else {
                    Spacer(modifier = Modifier.width(1.dp))
                }

                if (currentStep < 7) {
                    Button(
                        onClick = { currentStep++ },
                        colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = Color.White)
                    ) {
                        Text("NEXT STEP", fontWeight = FontWeight.Bold)
                    }
                } else {
                    Button(
                        onClick = {
                            viewModel.createCampaign(
                                name = campaignName,
                                asset = selectedAsset,
                                timeframe = selectedTimeframe,
                                objective = objective,
                                hypothesis = hypothesis
                            )
                            onCampaignCreated()
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = StatusGreen, contentColor = Color.White)
                    ) {
                        Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("START CAMPAIGN", fontWeight = FontWeight.Bold)
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}
