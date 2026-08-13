package com.example.data.local

import org.junit.Assert.assertEquals
import org.junit.Test

class PipelineRunEntityTest {

    @Test
    fun `PipelineRunEntity can be created`() {
        val entity = PipelineRunEntity(
            runId = "run-1",
            pipelineName = "backtest",
            status = "running",
            startedAt = "2024-01-01T00:00:00Z",
            completedAt = null,
            duration = 1.5,
            error = null,
            fetchedAt = 123456789L
        )
        assertEquals("run-1", entity.runId)
        assertEquals("backtest", entity.pipelineName)
        assertEquals(123456789L, entity.fetchedAt)
    }
}
