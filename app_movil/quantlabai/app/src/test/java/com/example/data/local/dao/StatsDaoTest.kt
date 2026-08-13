package com.example.data.local.dao

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.example.data.local.QuantLabDatabase
import com.example.data.local.StatsEntity
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class StatsDaoTest {

    private lateinit var database: QuantLabDatabase
    private lateinit var dao: StatsDao

    @Before
    fun setup() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        database = Room.inMemoryDatabaseBuilder(context, QuantLabDatabase::class.java)
            .fallbackToDestructiveMigration(false)
            .build()
        dao = database.statsDao()
    }

    @Test
    fun `insert and getLatest returns stats`() = runBlocking {
        val entity = StatsEntity(
            generatedAt = "2024-01-01T00:00:00Z",
            sharpeMean = 1.5,
            sharpeStd = 0.3,
            maxDrawdownPct = 10.0,
            winRateMean = 0.55,
            totalTrades = 100,
            benchmarkComparison = null,
            totalCampaigns = 5,
            totalPipelineRuns = 10,
            fetchedAt = 123456789L
        )
        dao.insert(entity)
        val latest = dao.getLatest()
        assertEquals(1.5, latest?.sharpeMean ?: 0.0, 0.01)
    }
}
