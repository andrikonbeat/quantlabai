package com.example.data.remote.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class ApiEnvelope<T>(
    @Json(name = "success") val success: Boolean,
    @Json(name = "data") val data: T?
)

@JsonClass(generateAdapter = true)
data class ApiHealth(
    @Json(name = "status") val status: String,
    @Json(name = "version") val version: String
)

@JsonClass(generateAdapter = true)
data class ApiCampaign(
    @Json(name = "campaign_id") val campaignId: String,
    val name: String,
    @Json(name = "market") val market: String,
    val timeframe: String,
    val sharpe: Double?,
    @Json(name = "profit_factor") val profitFactor: Double?,
    @Json(name = "win_rate") val winRate: Double?,
    val status: String,
    @Json(name = "total_return") val totalReturn: Double?,
    val metrics: ApiCampaignMetrics?,
    val tags: List<String>?,
    val created: String?,
    val path: String?
)

@JsonClass(generateAdapter = true)
data class ApiCampaignMetrics(
    @Json(name = "sharpe_ratio") val sharpeRatio: Double?,
    @Json(name = "profit_factor") val profitFactor: Double?,
    @Json(name = "win_rate") val winRate: Double?,
    @Json(name = "max_drawdown") val maxDrawdown: Double?,
    @Json(name = "total_trades") val totalTrades: Int?,
    @Json(name = "net_profit") val netProfit: String?
)

@JsonClass(generateAdapter = true)
data class ApiCampaignDetail(
    @Json(name = "campaign_id") val campaignId: String,
    val name: String,
    @Json(name = "market") val market: String,
    val timeframe: String,
    val sharpe: Double?,
    @Json(name = "profit_factor") val profitFactor: Double?,
    @Json(name = "win_rate") val winRate: Double?,
    val status: String,
    @Json(name = "total_return") val totalReturn: Double?,
    val metrics: ApiCampaignMetrics?,
    val tags: List<String>?,
    val created: String?,
    val path: String?,
    @Json(name = "equity_curve") val equityCurve: List<Any>?,
    val trades: List<Any>?,
    val statistics: Map<String, Any>?,
    val phases: List<Any>?
)

@JsonClass(generateAdapter = true)
data class ApiStageRun(
    val name: String,
    val status: String,
    @Json(name = "started_at") val startedAt: String,
    @Json(name = "completed_at") val completedAt: String?,
    val duration: Double,
    val error: String?,
    val output: Any?
)

@JsonClass(generateAdapter = true)
data class ApiPipelineRun(
    @Json(name = "run_id") val runId: String,
    @Json(name = "pipeline_name") val pipelineName: String,
    val status: String,
    @Json(name = "started_at") val startedAt: String,
    @Json(name = "completed_at") val completedAt: String?,
    val duration: Double,
    val error: String?,
    val stages: List<ApiStageRun>?,
    @Json(name = "config_snapshot") val configSnapshot: Map<String, Any>?,
    val artifacts: Map<String, String>?
)

@JsonClass(generateAdapter = true)
data class ApiStats(
    @Json(name = "sharpe_mean") val sharpeMean: Double,
    @Json(name = "sharpe_std") val sharpeStd: Double,
    @Json(name = "max_drawdown_pct") val maxDrawdownPct: Double,
    @Json(name = "win_rate_mean") val winRateMean: Double,
    @Json(name = "total_trades") val totalTrades: Int,
    @Json(name = "benchmark_comparison") val benchmarkComparison: Any?,
    @Json(name = "total_campaigns") val totalCampaigns: Int,
    @Json(name = "total_pipeline_runs") val totalPipelineRuns: Int,
    @Json(name = "generated_at") val generatedAt: String
)
