package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
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
import com.example.data.model.ApprovalStatus
import com.example.ui.QuantLabViewModel
import com.example.ui.components.StatusBadge
import com.example.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalsScreen(
    viewModel: QuantLabViewModel,
    onNavigateToStrategy: (String) -> Unit,
    onBackClick: () -> Unit
) {
    val approvals by viewModel.approvals.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "APPROVAL QUEUE",
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
                .testTag("approvals_screen")
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(16.dp),
                modifier = Modifier.fillMaxSize()
            ) {
                items(approvals) { item ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, if (item.status == ApprovalStatus.PENDING) StatusAmber else GraphiteBorder, RoundedCornerShape(12.dp)),
                        colors = CardDefaults.cardColors(containerColor = GraphiteCard)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = item.requestType.name,
                                    color = ElectricCyan,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    fontFamily = FontFamily.Monospace
                                )
                                StatusBadge(
                                    text = item.status.name,
                                    statusColor = when (item.status) {
                                        ApprovalStatus.PENDING -> StatusAmber
                                        ApprovalStatus.APPROVED -> StatusGreen
                                        ApprovalStatus.REJECTED -> StatusRed
                                    },
                                    bgColor = when (item.status) {
                                        ApprovalStatus.PENDING -> StatusAmberBg
                                        ApprovalStatus.APPROVED -> StatusGreenBg
                                        ApprovalStatus.REJECTED -> StatusRedBg
                                    }
                                )
                            }

                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = item.title,
                                color = TextPrimary,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )

                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "METRICS SUMMARY",
                                color = TextMuted,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                            Text(
                                text = item.metricsSummary,
                                color = ElectricCyan,
                                fontSize = 13.sp,
                                fontFamily = FontFamily.Monospace
                            )

                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "RISK / IMPACT",
                                color = TextMuted,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                            Text(
                                text = item.riskImpact,
                                color = TextSecondary,
                                fontSize = 13.sp
                            )

                            if (item.status == ApprovalStatus.PENDING) {
                                Spacer(modifier = Modifier.height(16.dp))
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.End
                                ) {
                                    OutlinedButton(
                                        onClick = { onNavigateToStrategy(item.strategyId) },
                                        border = BorderStroke(1.dp, GraphiteBorder),
                                        colors = ButtonDefaults.outlinedButtonColors(contentColor = TextPrimary),
                                        shape = RoundedCornerShape(8.dp)
                                    ) {
                                        Text("REVIEW", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                    }
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Button(
                                        onClick = { viewModel.approveItem(item.id) },
                                        colors = ButtonDefaults.buttonColors(containerColor = StatusGreen, contentColor = Color.White),
                                        shape = RoundedCornerShape(8.dp)
                                    ) {
                                        Text("APPROVE", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                    }
                                }
                            }
                        }
                    }
                }
                item { Spacer(modifier = Modifier.height(40.dp)) }
            }
        }
    }
}
