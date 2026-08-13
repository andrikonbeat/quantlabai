package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import com.example.ui.components.LivePulseIndicator
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.ChatContextType
import com.example.data.model.ChatMessage
import com.example.data.model.ChatSender
import com.example.ui.QuantLabViewModel
import com.example.ui.theme.*
import kotlinx.coroutines.launch

private data class ConversationHistoryItem(
    val id: String,
    val title: String,
    val preview: String,
    val time: String,
    val msgCount: String
)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ChatScreen(
    viewModel: QuantLabViewModel,
    onOpenCodeViewClick: () -> Unit,
    onNavigateToStrategy: (String) -> Unit
) {
    val messages by viewModel.chatMessages.collectAsState()
    val activeContext by viewModel.chatContext.collectAsState()
    val activeOrchestrator by viewModel.activeOrchestrator.collectAsState()
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope = rememberCoroutineScope()

    var inputMessage by remember { mutableStateOf("") }
    var showAttachmentSheet by remember { mutableStateOf(false) }
    var showOrchestratorMenu by remember { mutableStateOf(false) }
    var selectedConversationId by remember { mutableStateOf<String?>("conv_1") }
    val listState = rememberLazyListState()

    val filteredMessages = messages.filter {
        activeContext == ChatContextType.GLOBAL || it.contextType == activeContext
    }

    LaunchedEffect(filteredMessages.size) {
        if (filteredMessages.isNotEmpty()) {
            listState.animateScrollToItem(filteredMessages.size - 1)
        }
    }

    val conversationsHistory = remember {
        listOf(
            ConversationHistoryItem(
                id = "conv_1",
                title = "What are some useful CLI...",
                preview = "What are some useful CLI tools I could build?",
                time = "1h ago",
                msgCount = "1 msg"
            ),
            ConversationHistoryItem(
                id = "conv_2",
                title = "Explain how neural netwo...",
                preview = "Explain how neural networks learn in simple terms",
                time = "8h ago",
                msgCount = "1 msg"
            ),
            ConversationHistoryItem(
                id = "conv_3",
                title = "Teach me the basics of...",
                preview = "Teach me the basics of Rust ownership and borrowing",
                time = "1d ago",
                msgCount = "3 msg"
            ),
            ConversationHistoryItem(
                id = "conv_4",
                title = "Walk me through how DNS...",
                preview = "Walk me through how DNS resolution works",
                time = "2d ago",
                msgCount = "2 msg"
            )
        )
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        gesturesEnabled = true,
        drawerContent = {
            ModalDrawerSheet(
                drawerContainerColor = Color(0xFF05080A),
                drawerContentColor = Color.White,
                modifier = Modifier.width(300.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .statusBarsPadding()
                        .padding(16.dp)
                ) {
                    // Drawer Header row (without logo or title text as requested)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.End,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        IconButton(onClick = { scope.launch { drawerState.close() } }) {
                            Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextMuted)
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // High contrast + NEW CHAT button
                    Surface(
                        color = StatusGreen,
                        shape = RoundedCornerShape(6.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                selectedConversationId = null
                                scope.launch { drawerState.close() }
                                viewModel.sendChatMessage("Help me learn")
                            }
                    ) {
                        Row(
                            modifier = Modifier.padding(vertical = 12.dp),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(imageVector = Icons.Default.Add, contentDescription = null, tint = Color.Black, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "NEW CHAT",
                                color = Color.Black,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))
                    HorizontalDivider(color = Color(0xFF141F18))
                    Spacer(modifier = Modifier.height(12.dp))

                    // History list
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                        modifier = Modifier.weight(1f)
                    ) {
                        items(conversationsHistory) { item ->
                            val isSelected = selectedConversationId == item.id
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        selectedConversationId = item.id
                                        scope.launch { drawerState.close() }
                                        viewModel.sendChatMessage(item.preview)
                                    }
                                    .padding(vertical = 4.dp)
                            ) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = item.title,
                                        color = if (isSelected) StatusGreen else TextPrimary,
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Bold,
                                        fontFamily = FontFamily.Monospace
                                    )
                                    Text(
                                        text = item.time,
                                        color = TextMuted,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                                Spacer(modifier = Modifier.height(2.dp))
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = item.preview,
                                        color = TextMuted,
                                        fontSize = 11.sp,
                                        fontFamily = FontFamily.Monospace,
                                        maxLines = 1,
                                        modifier = Modifier.weight(1f)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        text = item.msgCount,
                                        color = TextMuted,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .background(Color(0xFF050709))
                .imePadding()
        ) {
            // Top Bar in Chat Screen with High-Tech Orchestrator Selector
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = { scope.launch { drawerState.open() } }) {
                    Icon(
                        imageVector = Icons.Default.Menu,
                        contentDescription = "Open Drawer",
                        tint = TextPrimary,
                        modifier = Modifier.size(22.dp)
                    )
                }

                // Interactive Orchestrator Selector Pill
                Box {
                    Surface(
                        color = Color.Transparent,
                        shape = RoundedCornerShape(20.dp),
                        border = BorderStroke(1.dp, Brush.horizontalGradient(listOf(StatusGreen.copy(alpha = 0.8f), ElectricCyan.copy(alpha = 0.8f)))),
                        modifier = Modifier
                            .background(
                                brush = Brush.horizontalGradient(listOf(Color(0xFF0D2115), Color(0xFF07150E))),
                                shape = RoundedCornerShape(20.dp)
                            )
                            .clickable { showOrchestratorMenu = true }
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp)
                        ) {
                            LivePulseIndicator(sizeDp = 6, color = StatusGreen)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = activeOrchestrator,
                                color = StatusGreen,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Icon(
                                imageVector = Icons.Default.Tune,
                                contentDescription = "Orchestrator Selector",
                                tint = ElectricCyan,
                                modifier = Modifier.size(14.dp)
                            )
                            Spacer(modifier = Modifier.width(2.dp))
                            Icon(
                                imageVector = Icons.Default.ArrowDropDown,
                                contentDescription = null,
                                tint = StatusGreen,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                    }

                    DropdownMenu(
                        expanded = showOrchestratorMenu,
                        onDismissRequest = { showOrchestratorMenu = false },
                        modifier = Modifier
                            .width(260.dp)
                            .background(Color(0xFF09120D))
                            .border(
                                1.dp,
                                Brush.horizontalGradient(listOf(StatusGreen.copy(alpha = 0.6f), ElectricCyan.copy(alpha = 0.6f))),
                                RoundedCornerShape(12.dp)
                            )
                            .clip(RoundedCornerShape(12.dp))
                    ) {
                        val orchestrators = listOf(
                            Triple("QuantLab-Orchestrator", "Alpha & Strategy Pipeline", Icons.Default.AutoGraph),
                            Triple("Guardián-Orchestrator", "Risk Sentinel & Safety Guard", Icons.Default.Shield),
                            Triple("OpenMono-Orchestrator", "Core Autonomous Framework", Icons.Default.Memory),
                            Triple("Scalper-Orchestrator", "High-Frequency HFT Execution", Icons.Default.Bolt)
                        )

                        orchestrators.forEach { (orch, desc, icon) ->
                            val isSelected = orch == activeOrchestrator
                            DropdownMenuItem(
                                text = {
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        Icon(
                                            imageVector = icon,
                                            contentDescription = orch,
                                            tint = if (isSelected) StatusGreen else TextMuted,
                                            modifier = Modifier.size(18.dp)
                                        )
                                        Spacer(modifier = Modifier.width(10.dp))
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                text = orch,
                                                color = if (isSelected) StatusGreen else TextPrimary,
                                                fontFamily = FontFamily.Monospace,
                                                fontSize = 12.sp,
                                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                                            )
                                            Text(
                                                text = desc,
                                                color = TextMuted,
                                                fontSize = 10.sp,
                                                fontFamily = FontFamily.Monospace
                                            )
                                        }
                                        if (isSelected) {
                                            Spacer(modifier = Modifier.width(6.dp))
                                            Icon(
                                                imageVector = Icons.Default.Check,
                                                contentDescription = "Selected",
                                                tint = StatusGreen,
                                                modifier = Modifier.size(16.dp)
                                            )
                                        }
                                    }
                                },
                                onClick = {
                                    viewModel.setOrchestrator(orch)
                                    showOrchestratorMenu = false
                                },
                                modifier = Modifier.background(
                                    if (isSelected) StatusGreenBg.copy(alpha = 0.4f) else Color.Transparent
                                )
                            )
                        }
                    }
                }

                IconButton(onClick = { /* Settings action */ }) {
                    Icon(
                        imageVector = Icons.Default.Settings,
                        contentDescription = "Settings",
                        tint = TextMuted,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            // Clean Terminal Interface Sub-header
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp)
            ) {
                Text(
                    text = "> QUANTLAB ORCHESTRATOR TERMINAL",
                    color = TextPrimary,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = "// active engine: $activeOrchestrator",
                    color = StatusGreen,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Main Chat Area & Preset Prompts List
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Preset Prompts Card Stack matching Screenshot 1 & 2
                item {
                    val presetPrompts = listOf(
                        "Explain how neural networks learn in simple terms",
                        "Teach me the basics of Rust ownership and borrowing",
                        "Walk me through how DNS resolution works"
                    )

                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        presetPrompts.forEach { promptText ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(IntrinsicSize.Min)
                                    .clickable { viewModel.sendChatMessage(promptText) },
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                // Solid green vertical left indicator covering full prompt height
                                Box(
                                    modifier = Modifier
                                        .width(3.dp)
                                        .fillMaxHeight()
                                        .background(StatusGreen)
                                )
                                Spacer(modifier = Modifier.width(12.dp))

                                // Content box with green square bullet and monospace prompt
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier
                                        .weight(1f)
                                        .background(Color(0xFF080D0A), RoundedCornerShape(2.dp))
                                        .border(0.5.dp, Color(0xFF14241B), RoundedCornerShape(2.dp))
                                        .padding(horizontal = 12.dp, vertical = 12.dp)
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .size(6.dp)
                                            .background(StatusGreen)
                                    )
                                    Spacer(modifier = Modifier.width(10.dp))
                                    Text(
                                        text = promptText,
                                        color = TextPrimary,
                                        fontSize = 13.sp,
                                        fontFamily = FontFamily.Monospace,
                                        lineHeight = 18.sp
                                    )
                                }
                            }
                        }
                    }
                }

                // Messages list
                items(filteredMessages) { msg ->
                    OpenMonoMessageBubble(
                        message = msg,
                        onActionClick = { actionText ->
                            viewModel.sendChatMessage(actionText)
                        }
                    )
                }

                item { Spacer(modifier = Modifier.height(12.dp)) }
            }

            // Input Box matching Screenshot 1 & 2
            Surface(
                color = Color(0xFF080D0A),
                border = BorderStroke(1.dp, Color(0xFF1E3A2B)),
                shape = RoundedCornerShape(20.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 10.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        OutlinedTextField(
                            value = inputMessage,
                            onValueChange = { inputMessage = it },
                            placeholder = {
                                Text(
                                    text = "Ask > $activeOrchestrator",
                                    color = TextMuted.copy(alpha = 0.7f),
                                    fontSize = 14.sp,
                                    fontFamily = FontFamily.Monospace
                                )
                            },
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag("chat_input_field"),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedContainerColor = Color.Transparent,
                                unfocusedContainerColor = Color.Transparent,
                                focusedBorderColor = Color.Transparent,
                                unfocusedBorderColor = Color.Transparent,
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary
                            ),
                            textStyle = LocalTextStyle.current.copy(
                                color = TextPrimary,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 14.sp
                            ),
                            maxLines = 4
                        )
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    // Bottom controls inside input container: + on bottom-left, ↑ arrow on bottom-right
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        IconButton(
                            onClick = { showAttachmentSheet = true },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Add,
                                contentDescription = "Attach",
                                tint = TextMuted,
                                modifier = Modifier.size(20.dp)
                            )
                        }

                        Box(
                            modifier = Modifier
                                .size(34.dp)
                                .background(
                                    if (inputMessage.isNotBlank()) StatusGreen else Color(0xFF121D17),
                                    CircleShape
                                )
                                .clickable {
                                    if (inputMessage.isNotBlank()) {
                                        viewModel.sendChatMessage(inputMessage)
                                        inputMessage = ""
                                    }
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.ArrowUpward,
                                contentDescription = "Send",
                                tint = if (inputMessage.isNotBlank()) Color.Black else TextMuted,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                }
            }

            // Attachment Sheet
            if (showAttachmentSheet) {
                ModalBottomSheet(
                    onDismissRequest = { showAttachmentSheet = false },
                    containerColor = Color(0xFF09100C),
                    scrimColor = Color.Black.copy(alpha = 0.6f)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(20.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .align(Alignment.CenterHorizontally)
                                .width(36.dp)
                                .height(4.dp)
                                .background(StatusGreen.copy(alpha = 0.5f), RoundedCornerShape(2.dp))
                        )
                        Spacer(modifier = Modifier.height(20.dp))

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    showAttachmentSheet = false
                                    viewModel.sendChatMessage("Attached file: tick_data_EURUSD_M1.csv")
                                }
                                .padding(vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.AttachFile,
                                contentDescription = "Upload",
                                tint = TextPrimary,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(16.dp))
                            Text(
                                text = "Upload File",
                                color = TextPrimary,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Medium
                            )
                        }

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    showAttachmentSheet = false
                                    viewModel.sendChatMessage("Captured screenshot of chart setup.")
                                }
                                .padding(vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.PhotoCamera,
                                contentDescription = "Photo",
                                tint = TextPrimary,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(16.dp))
                            Text(
                                text = "Take Photo",
                                color = TextPrimary,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Medium
                            )
                        }
                        Spacer(modifier = Modifier.height(20.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun OpenMonoMessageBubble(
    message: ChatMessage,
    onActionClick: (String) -> Unit
) {
    val isUser = message.sender == ChatSender.USER
    val barColor = if (isUser) ElectricCyan else StatusGreen

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min)
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.Top
    ) {
        // Vertical accent line on left spanning 100% of the message height
        Box(
            modifier = Modifier
                .width(3.dp)
                .fillMaxHeight()
                .background(barColor)
        )
        Spacer(modifier = Modifier.width(12.dp))

        Column(modifier = Modifier.weight(1f)) {
            // Message Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = if (isUser) "> USER" else "> ${message.authorName}",
                    color = barColor,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    text = message.timestamp,
                    color = TextMuted,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
            }

            Spacer(modifier = Modifier.height(4.dp))

            Text(
                text = message.content,
                color = TextPrimary,
                fontSize = 13.sp,
                fontFamily = FontFamily.Monospace,
                lineHeight = 20.sp
            )

            if (message.actionText != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Surface(
                    color = StatusGreen,
                    shape = RoundedCornerShape(2.dp),
                    modifier = Modifier.clickable { onActionClick(message.actionText) }
                ) {
                    Text(
                        text = "[ ▶ ] ${message.actionText}",
                        color = Color.Black,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                    )
                }
            }
        }
    }
}
