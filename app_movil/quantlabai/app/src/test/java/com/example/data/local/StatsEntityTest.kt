package com.example.data.local

import org.junit.Assert.assertEquals
import org.junit.Test

class StatsEntityTest {

    @Test
    fun `StatsEntity can be created`() {
        val entity = StatsEntity(
            sharpeMean = 1.5,
            sharpeStd = 0.3,
            maxDrawdownPct = 10.0,
            winRateMean = 0.55,
            totalTrades = 100,
            benchmarkComparison = null,
            totalCampaigns = 5,
            totalPipelineRuns = 10,
            generatedAt = "2024-01-01T00:00:00Z",
            fetchedAt = 123456789L
        )
        assertEquals(1.5, entity.sharpeMean, 0.01)
        assertEquals(123456789L, entity.fetchedAt)
    }
}
