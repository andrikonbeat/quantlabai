package com.example.data.model

import org.junit.Assert.assertEquals
import org.junit.Test

class PipelineRunStatsTest {

    @Test
    fun `PipelineRun has all fields`() {
        val run = PipelineRun(
            runId = "run-1",
            pipelineName = "test",
            status = "running",
            startedAt = "2024-01-01T00:00:00Z",
            completedAt = null,
            duration = 1.5,
            error = null
        )
        assertEquals("run-1", run.runId)
        assertEquals("test", run.pipelineName)
        assertEquals("running", run.status)
        assertEquals("2024-01-01T00:00:00Z", run.startedAt)
        assertEquals(null, run.completedAt)
        assertEquals(1.5, run.duration, 0.01)
        assertEquals(null, run.error)
    }

    @Test
    fun `Stats has all fields`() {
        val stats = Stats(
            sharpeMean = 1.5,
            sharpeStd = 0.3,
            maxDrawdownPct = 10.0,
            winRateMean = 0.55,
            totalTrades = 100,
            benchmarkComparison = null,
            totalCampaigns = 5,
            totalPipelineRuns = 10,
            generatedAt = "2024-01-01T00:00:00Z"
        )
        assertEquals(1.5, stats.sharpeMean, 0.01)
        assertEquals(0.3, stats.sharpeStd, 0.01)
        assertEquals(10.0, stats.maxDrawdownPct, 0.01)
        assertEquals(0.55, stats.winRateMean, 0.01)
        assertEquals(100, stats.totalTrades)
        assertEquals(5, stats.totalCampaigns)
        assertEquals(10, stats.totalPipelineRuns)
        assertEquals("2024-01-01T00:00:00Z", stats.generatedAt)
    }
}
