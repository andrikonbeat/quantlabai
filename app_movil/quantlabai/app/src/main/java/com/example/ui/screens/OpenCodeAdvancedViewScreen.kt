package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
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
import com.example.ui.QuantLabViewModel
import com.example.ui.theme.*

@Composable
fun OpenCodeAdvancedViewScreen(
    viewModel: QuantLabViewModel,
    onBackClick: () -> Unit
) {
    var terminalInput by remember { mutableStateOf("") }
    var logsList by remember {
        mutableStateOf(
            listOf(
                "01:42:01 [SYS] OpenCode Sub-Agent Execution Terminal v2.4 initialized",
                "01:42:02 [SYS] Orchestrator cluster active on campaign #EURUSD-H1",
                "01:42:03 [OK] Research Agent: Completed macro sentiment analysis (Score: +0.68)",
                "01:42:04 [OK] Hypothesis Agent: Formulating entry triggers for H-042 mean reversion",
                "01:42:05 [RUN] SQX Agent: Running genetic strategy evolution (5,000 targets)",
                "          └─ Evaluated 4,820 candidate building blocks across 16 CPU cores",
                "          └─ Filtered 86 strategies due to excessive trade frequency (>2,000/yr)",
                "01:42:08 [OK] Validation Agent: OOS Period 4/6 passed robustness check (Efficiency: 84%)",
                "01:42:10 [OK] Portfolio Agent: Pearson correlation matrix calculated (Max: 0.18 < 0.25)",
                "01:42:12 [WARN] Replacement Agent: Monitoring live strategy #7012 drawdown (-14.2%)",
                "          └─ Candidate STRAT-8421 queued as optimal replacement",
                "01:42:15 [SYS] All 7 sub-agents operating within safety parameters",
                "01:42:16 [READY] Listening for sub-agent orchestration commands..."
            )
        )
    }

    val listState = rememberLazyListState()

    LaunchedEffect(logsList.size) {
        if (logsList.isNotEmpty()) {
            listState.animateScrollToItem(logsList.size - 1)
        }
    }

    Scaffold(
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .background(Color(0xFF030507))
                    .border(1.dp, StatusGreen.copy(alpha = 0.3f))
                    .padding(horizontal = 12.dp, vertical = 8.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.weight(1f)
                    ) {
                        IconButton(onClick = onBackClick, modifier = Modifier.size(24.dp)) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = TextSecondary)
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "TTY01::OPENCODE_CONSOLE",
                            color = StatusGreen,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1
                        )
                    }
                    Text(
                        text = "[ 7 AGENTS ONLINE ]",
                        color = StatusGreen,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        },
        bottomBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF030507))
                    .border(1.dp, GraphiteBorder)
                    .padding(horizontal = 12.dp, vertical = 8.dp)
                    .navigationBarsPadding()
                    .imePadding()
            ) {
                // Minimalist Prompt Line
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    color = Color(0xFF080D0A),
                    border = BorderStroke(1.dp, StatusGreen.copy(alpha = 0.4f)),
                    shape = RoundedCornerShape(2.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = "> ",
                            color = StatusGreen,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        OutlinedTextField(
                            value = terminalInput,
                            onValueChange = { terminalInput = it },
                            placeholder = { Text("enter command or prompt...", color = TextMuted, fontSize = 12.sp, fontFamily = FontFamily.Monospace) },
                            modifier = Modifier
                                .weight(1f)
                                .testTag("opencode_cmd_input"),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedContainerColor = Color.Transparent,
                                unfocusedContainerColor = Color.Transparent,
                                focusedBorderColor = Color.Transparent,
                                unfocusedBorderColor = Color.Transparent,
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary
                            ),
                            textStyle = LocalTextStyle.current.copy(fontFamily = FontFamily.Monospace, fontSize = 12.sp),
                            singleLine = true
                        )

                        Surface(
                            color = StatusGreen,
                            shape = RoundedCornerShape(2.dp),
                            modifier = Modifier
                                .clickable {
                                    if (terminalInput.isNotBlank()) {
                                        logsList = logsList + "01:42:20 [USR] $terminalInput" + "01:42:21 [RUN] Executing sub-agent directive..."
                                        terminalInput = ""
                                    }
                                }
                        ) {
                            Text(
                                text = "RUN ↵",
                                color = Color.Black,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "SYS::CLAUDE_OPUS_4.5 | SHIFT+ENTER: MULTILINE",
                        color = TextMuted,
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace
                    )

                    Text(
                        text = "[ CLR ]",
                        color = TextMuted,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.clickable { logsList = emptyList() }
                    )
                }
            }
        },
        containerColor = Color(0xFF030507)
    ) { innerPadding ->
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 12.dp, vertical = 8.dp)
                .testTag("opencode_advanced_view_screen"),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            items(logsList.size) { idx ->
                val line = logsList[idx]
                val color = when {
                    line.contains("[SYS]") -> StatusBlue
                    line.contains("[OK]") -> StatusGreen
                    line.contains("[RUN]") -> ElectricCyan
                    line.contains("[WARN]") -> StatusAmber
                    line.contains("[ERR]") -> StatusRed
                    line.contains("[USR]") -> StatusGreen
                    else -> TextPrimary
                }

                Text(
                    text = line,
                    color = color,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    lineHeight = 16.sp
                )
            }
        }
    }
}
