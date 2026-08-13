package com.example.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "pipeline_runs")
data class PipelineRunEntity(
    @PrimaryKey val runId: String,
    val pipelineName: String,
    val status: String,
    val startedAt: String,
    val completedAt: String?,
    val duration: Double,
    val error: String?,
    val fetchedAt: Long
)
