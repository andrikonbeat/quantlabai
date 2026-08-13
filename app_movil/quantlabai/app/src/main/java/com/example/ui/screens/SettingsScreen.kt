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
import com.example.data.model.AutonomyPolicy
import com.example.ui.QuantLabViewModel
import com.example.ui.components.StatusBadge
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: QuantLabViewModel,
    onBackClick: () -> Unit
) {
    val autonomyPolicy by viewModel.autonomyPolicy.collectAsState()

    var policy by remember { mutableStateOf(autonomyPolicy) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "SETTINGS & AUTONOMY CONTROL",
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
                .testTag("settings_screen"),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Autonomy Policy Header
            item {
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
                            Text(
                                text = "AUTONOMY POLICY MATRIX",
                                color = ElectricCyan,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                            StatusBadge(text = "HUMAN-IN-THE-LOOP", statusColor = StatusAmber, bgColor = StatusAmberBg)
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "Enforces operational boundary limits between autonomous agent workflows and human operator approvals.",
                            color = TextSecondary,
                            fontSize = 12.sp
                        )

                        Spacer(modifier = Modifier.height(16.dp))

                        PolicyToggleRow(
                            title = "Market & Macro Research",
                            isAuto = policy.researchAuto,
                            onToggle = { policy = policy.copy(researchAuto = it) }
                        )
                        PolicyToggleRow(
                            title = "Strategy Generation (SQX)",
                            isAuto = policy.generationAuto,
                            onToggle = { policy = policy.copy(generationAuto = it) }
                        )
                        PolicyToggleRow(
                            title = "Robustness & WF Validation",
                            isAuto = policy.validationAuto,
                            onToggle = { policy = policy.copy(validationAuto = it) }
                        )
                        PolicyToggleRow(
                            title = "Replacement Search",
                            isAuto = policy.replacementSearchAuto,
                            onToggle = { policy = policy.copy(replacementSearchAuto = it) }
                        )

                        HorizontalDivider(color = GraphiteBorder, modifier = Modifier.padding(vertical = 10.dp))

                        PolicyToggleRow(
                            title = "Portfolio Inclusion",
                            isAuto = !policy.portfolioInclusionApproval,
                            autoLabel = "AUTO",
                            manualLabel = "APPROVAL REQUIRED",
                            onToggle = { policy = policy.copy(portfolioInclusionApproval = !it) }
                        )
                        PolicyToggleRow(
                            title = "Live Deployment Assignment",
                            isAuto = !policy.liveDeploymentApproval,
                            autoLabel = "AUTO",
                            manualLabel = "APPROVAL REQUIRED",
                            onToggle = { policy = policy.copy(liveDeploymentApproval = !it) }
                        )
                        PolicyToggleRow(
                            title = "Strategy Decommissioning",
                            isAuto = !policy.strategyDeletionApproval,
                            autoLabel = "AUTO",
                            manualLabel = "APPROVAL REQUIRED",
                            onToggle = { policy = policy.copy(strategyDeletionApproval = !it) }
                        )

                        Spacer(modifier = Modifier.height(14.dp))
                        Button(
                            onClick = { viewModel.updateAutonomyPolicy(policy) },
                            colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = androidx.compose.ui.graphics.Color.White),
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("SAVE AUTONOMY POLICY", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            // Connection Settings
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, GraphiteBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("SYSTEM CONNECTIONS", color = TextMuted, fontSize = 11.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        Spacer(modifier = Modifier.height(10.dp))
                        SettingValueRow("OpenCode Endpoint", "ws://10.0.2.2:8080/opencode")
                        SettingValueRow("StrategyQuant X Server", "https://sqx.quantlab.internal")
                        SettingValueRow("Tick Data Source", "Dukascopy FX High Precision")
                        SettingValueRow("AI Model Engine", "Gemini 3.6 / Local DeepSeek R1")
                    }
                }
            }

            item { Spacer(modifier = Modifier.height(40.dp)) }
        }
    }
}

@Composable
private fun PolicyToggleRow(
    title: String,
    isAuto: Boolean,
    autoLabel: String = "AUTO",
    manualLabel: String = "HUMAN APPROVAL",
    onToggle: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = title,
            color = TextPrimary,
            fontSize = 13.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.weight(1f)
        )
        Spacer(modifier = Modifier.width(12.dp))
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.End
        ) {
            Surface(
                color = if (isAuto) StatusGreenBg else StatusAmberBg,
                shape = RoundedCornerShape(2.dp),
                border = BorderStroke(1.dp, if (isAuto) StatusGreen.copy(alpha = 0.5f) else StatusAmber.copy(alpha = 0.5f))
            ) {
                Text(
                    text = if (isAuto) autoLabel else manualLabel,
                    color = if (isAuto) StatusGreen else StatusAmber,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 3.dp)
                )
            }
            Spacer(modifier = Modifier.width(10.dp))
            Switch(
                checked = isAuto,
                onCheckedChange = onToggle,
                colors = SwitchDefaults.colors(
                    checkedThumbColor = androidx.compose.ui.graphics.Color.Black,
                    checkedTrackColor = StatusGreen,
                    uncheckedThumbColor = androidx.compose.ui.graphics.Color.Black,
                    uncheckedTrackColor = StatusAmber
                )
            )
        }
    }
}

@Composable
private fun SettingValueRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = TextSecondary, fontSize = 12.sp, modifier = Modifier.weight(1f))
        Spacer(modifier = Modifier.width(12.dp))
        Text(value, color = ElectricCyan, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
    }
}
