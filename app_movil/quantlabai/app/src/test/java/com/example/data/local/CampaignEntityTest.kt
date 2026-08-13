package com.example.data.local

import org.junit.Assert.assertEquals
import org.junit.Test

class CampaignEntityTest {

    @Test
    fun `CampaignEntity can be created`() {
        val entity = CampaignEntity(
            id = "CAMP-1",
            name = "Test Campaign",
            asset = "EURUSD",
            timeframe = "H1",
            objective = "test",
            hypothesis = "H-1",
            progressPct = 50,
            currentStage = "GENERATION",
            activeAgents = 2,
            waitingAgents = 0,
            generatedCount = 100,
            passedFiltersCount = 10,
            status = "ACTIVE",
            lastEvent = "started",
            updatedAt = "13:00",
            fetchedAt = 123456789L
        )
        assertEquals("CAMP-1", entity.id)
        assertEquals("Test Campaign", entity.name)
        assertEquals(123456789L, entity.fetchedAt)
    }
}
