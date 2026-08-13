package com.example.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.*
import com.example.data.model.ChatContextType
import com.example.ui.components.CoderCurvedNavigationBar
import com.example.ui.screens.*
import com.example.ui.theme.*

sealed class Screen(val route: String, val title: String, val icon: ImageVector) {
    object Dashboard : Screen("dashboard", "Dashboard", Icons.Default.GridView)
    object Campaigns : Screen("campaigns", "Campaigns", Icons.Default.Timeline)
    object Chat : Screen("chat", "Chat", Icons.AutoMirrored.Filled.Chat)
    object Agents : Screen("agents", "Agents", Icons.Default.SmartToy)
    object More : Screen("more", "More", Icons.Default.Menu)
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun QuantLabApp(
    viewModel: QuantLabViewModel = viewModel()
) {
    val navController = rememberNavController()
    var showMoreBottomSheet by remember { mutableStateOf(false) }

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    val bottomBarRoutes = listOf(
        Screen.Dashboard.route,
        Screen.Campaigns.route,
        Screen.Chat.route,
        Screen.Agents.route,
        Screen.More.route
    )

    val isImeVisible = WindowInsets.isImeVisible
    val showBottomBar = (currentRoute in bottomBarRoutes || currentRoute == null) && !isImeVisible

    if (showMoreBottomSheet) {
        ModalBottomSheet(
            onDismissRequest = { showMoreBottomSheet = false },
            containerColor = GraphiteCard,
            contentColor = TextPrimary
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(20.dp)
            ) {
                Text(
                    text = "QUANTLAB CONTROL PLANE",
                    color = ElectricCyan,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(bottom = 16.dp)
                )

                MoreMenuItem(
                    icon = Icons.Default.Science,
                    title = "Strategy Laboratory",
                    subtitle = "Inspect and filter generated strategy candidates",
                    onClick = {
                        showMoreBottomSheet = false
                        navController.navigate("strategies")
                    }
                )

                MoreMenuItem(
                    icon = Icons.Default.VerifiedUser,
                    title = "Approval Queue",
                    subtitle = "Human-in-the-loop decision & risk requests",
                    onClick = {
                        showMoreBottomSheet = false
                        navController.navigate("approvals")
                    }
                )

                MoreMenuItem(
                    icon = Icons.Default.SwapHoriz,
                    title = "Replacement Engine",
                    subtitle = "Alpha degradation & strategy swap control",
                    onClick = {
                        showMoreBottomSheet = false
                        navController.navigate("replacement_engine")
                    }
                )

                MoreMenuItem(
                    icon = Icons.AutoMirrored.Filled.ListAlt,
                    title = "Global Activity Log",
                    subtitle = "System-wide event audit stream",
                    onClick = {
                        showMoreBottomSheet = false
                        navController.navigate("activity")
                    }
                )

                MoreMenuItem(
                    icon = Icons.Default.Dns,
                    title = "Infrastructure Health",
                    subtitle = "OpenCode, SQX, Cluster & DB status",
                    onClick = {
                        showMoreBottomSheet = false
                        navController.navigate("infrastructure")
                    }
                )

                MoreMenuItem(
                    icon = Icons.Default.Settings,
                    title = "Settings & Autonomy Policy",
                    subtitle = "System links & human boundary matrix",
                    onClick = {
                        showMoreBottomSheet = false
                        navController.navigate("settings")
                    }
                )

                Spacer(modifier = Modifier.height(20.dp))
            }
        }
    }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            if (showBottomBar) {
                val navItems = listOf(
                    Screen.Dashboard,
                    Screen.Campaigns,
                    Screen.Chat,
                    Screen.Agents,
                    Screen.More
                )
                CoderCurvedNavigationBar(
                    items = navItems,
                    currentRoute = currentRoute,
                    onItemSelected = { screen ->
                        if (screen == Screen.More) {
                            showMoreBottomSheet = true
                        } else {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    }
                )
            }
        },
        containerColor = GraphiteBackground
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Dashboard.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Dashboard.route) {
                DashboardScreen(
                    viewModel = viewModel,
                    onNavigateToCampaign = { campaignId ->
                        navController.navigate("campaign_detail/$campaignId")
                    },
                    onNavigateToStrategy = { strategyId ->
                        navController.navigate("strategy_detail/$strategyId")
                    },
                    onNavigateToNewCampaign = {
                        navController.navigate("new_campaign_wizard")
                    },
                    onNavigateToApprovals = {
                        navController.navigate("approvals")
                    }
                )
            }

            composable(Screen.Campaigns.route) {
                CampaignsScreen(
                    viewModel = viewModel,
                    onNavigateToCampaignDetail = { campaignId ->
                        navController.navigate("campaign_detail/$campaignId")
                    },
                    onNavigateToNewCampaign = {
                        navController.navigate("new_campaign_wizard")
                    }
                )
            }

            composable("campaign_detail/{campaignId}") { backStackEntry ->
                val campaignId = backStackEntry.arguments?.getString("campaignId") ?: "CAMP-027"
                CampaignDetailScreen(
                    campaignId = campaignId,
                    viewModel = viewModel,
                    onBackClick = { navController.popBackStack() },
                    onNavigateToAgent = { agentId ->
                        navController.navigate("agent_detail/$agentId")
                    },
                    onNavigateToStrategy = { strategyId ->
                        navController.navigate("strategy_detail/$strategyId")
                    },
                    onNavigateToChat = { contextType, contextName ->
                        viewModel.setChatContext(contextType, contextName)
                        navController.navigate(Screen.Chat.route)
                    }
                )
            }

            composable(Screen.Chat.route) {
                ChatScreen(
                    viewModel = viewModel,
                    onOpenCodeViewClick = {
                        navController.navigate("opencode_advanced_view")
                    },
                    onNavigateToStrategy = { strategyId ->
                        navController.navigate("strategy_detail/$strategyId")
                    }
                )
            }

            composable(Screen.Agents.route) {
                AgentsScreen(
                    viewModel = viewModel,
                    onNavigateToAgentDetail = { agentId ->
                        navController.navigate("agent_detail/$agentId")
                    }
                )
            }

            composable("agent_detail/{agentId}") { backStackEntry ->
                val agentId = backStackEntry.arguments?.getString("agentId") ?: "agent_sqx"
                AgentDetailScreen(
                    agentId = agentId,
                    viewModel = viewModel,
                    onBackClick = { navController.popBackStack() },
                    onNavigateToChat = { contextType, contextName ->
                        viewModel.setChatContext(contextType, contextName)
                        navController.navigate(Screen.Chat.route)
                    },
                    onNavigateToLogs = {
                        navController.navigate("opencode_advanced_view")
                    }
                )
            }

            composable("strategies") {
                StrategiesScreen(
                    viewModel = viewModel,
                    onNavigateToStrategyDetail = { strategyId ->
                        navController.navigate("strategy_detail/$strategyId")
                    },
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable("strategy_detail/{strategyId}") { backStackEntry ->
                val strategyId = backStackEntry.arguments?.getString("strategyId") ?: "STRAT-8421"
                StrategyDetailScreen(
                    strategyId = strategyId,
                    viewModel = viewModel,
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable("approvals") {
                ApprovalsScreen(
                    viewModel = viewModel,
                    onNavigateToStrategy = { strategyId ->
                        navController.navigate("strategy_detail/$strategyId")
                    },
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable("activity") {
                ActivityScreen(
                    viewModel = viewModel,
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable("replacement_engine") {
                ReplacementEngineScreen(
                    viewModel = viewModel,
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable("infrastructure") {
                InfrastructureScreen(
                    viewModel = viewModel,
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable("settings") {
                SettingsScreen(
                    viewModel = viewModel,
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable("opencode_advanced_view") {
                OpenCodeAdvancedViewScreen(
                    viewModel = viewModel,
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable("new_campaign_wizard") {
                NewCampaignWizardScreen(
                    viewModel = viewModel,
                    onBackClick = { navController.popBackStack() },
                    onCampaignCreated = {
                        navController.popBackStack()
                        navController.navigate(Screen.Campaigns.route)
                    }
                )
            }
        }
    }
}

@Composable
private fun MoreMenuItem(
    icon: ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
            .padding(vertical = 12.dp, horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Surface(
            color = GraphiteSurfaceVariant,
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.size(40.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(icon, contentDescription = title, tint = ElectricCyan, modifier = Modifier.size(20.dp))
            }
        }
        Spacer(modifier = Modifier.width(14.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(title, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
            Text(subtitle, color = TextSecondary, fontSize = 12.sp)
        }
        Icon(Icons.Default.ChevronRight, contentDescription = null, tint = TextMuted)
    }
}
