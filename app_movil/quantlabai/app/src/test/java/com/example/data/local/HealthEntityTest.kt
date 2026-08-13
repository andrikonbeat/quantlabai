package com.example.data.local

import org.junit.Assert.assertEquals
import org.junit.Test

class HealthEntityTest {

    @Test
    fun `HealthEntity can be created`() {
        val entity = HealthEntity(
            status = "ok",
            version = "1.0.0",
            fetchedAt = 123456789L
        )
        assertEquals("ok", entity.status)
        assertEquals("1.0.0", entity.version)
        assertEquals(123456789L, entity.fetchedAt)
    }
}
