package com.example.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "stats")
data class StatsEntity(
    @PrimaryKey val generatedAt: String,
    val sharpeMean: Double,
    val sharpeStd: Double,
    val maxDrawdownPct: Double,
    val winRateMean: Double,
    val totalTrades: Int,
    val benchmarkComparison: String?,
    val totalCampaigns: Int,
    val totalPipelineRuns: Int,
    val fetchedAt: Long
)
