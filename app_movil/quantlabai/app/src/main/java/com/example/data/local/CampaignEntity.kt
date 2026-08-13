package com.example.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "campaigns")
data class CampaignEntity(
    @PrimaryKey val id: String,
    val name: String,
    val asset: String,
    val timeframe: String,
    val objective: String,
    val hypothesis: String,
    val progressPct: Int,
    val currentStage: String,
    val activeAgents: Int,
    val waitingAgents: Int,
    val generatedCount: Int,
    val passedFiltersCount: Int,
    val status: String,
    val lastEvent: String,
    val updatedAt: String,
    val fetchedAt: Long
)
