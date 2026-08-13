package com.example.data.local.dao

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.example.data.local.CampaignEntity
import com.example.data.local.QuantLabDatabase
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class CampaignDaoTest {

    private lateinit var database: QuantLabDatabase
    private lateinit var dao: CampaignDao

    @Before
    fun setup() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        database = Room.inMemoryDatabaseBuilder(context, QuantLabDatabase::class.java)
            .fallbackToDestructiveMigration(false)
            .build()
        dao = database.campaignDao()
    }

    @Test
    fun `insert and getAll returns campaigns ordered by fetchedAt`() = runBlocking {
        val old = CampaignEntity(
            id = "CAMP-OLD",
            name = "Old",
            asset = "EURUSD",
            timeframe = "H1",
            objective = "",
            hypothesis = "",
            progressPct = 0,
            currentStage = "",
            activeAgents = 0,
            waitingAgents = 0,
            generatedCount = 0,
            passedFiltersCount = 0,
            status = "",
            lastEvent = "",
            updatedAt = "",
            fetchedAt = 1000L
        )
        val new = CampaignEntity(
            id = "CAMP-NEW",
            name = "New",
            asset = "EURUSD",
            timeframe = "H1",
            objective = "",
            hypothesis = "",
            progressPct = 0,
            currentStage = "",
            activeAgents = 0,
            waitingAgents = 0,
            generatedCount = 0,
            passedFiltersCount = 0,
            status = "",
            lastEvent = "",
            updatedAt = "",
            fetchedAt = 2000L
        )
        dao.insert(old)
        dao.insert(new)

        val all = dao.getAll().first()
        assertEquals(2, all.size)
        assertEquals("CAMP-NEW", all.first().id)
    }

    @Test
    fun `getById returns correct campaign`() = runBlocking {
        val entity = CampaignEntity(
            id = "CAMP-1",
            name = "Test",
            asset = "EURUSD",
            timeframe = "H1",
            objective = "",
            hypothesis = "",
            progressPct = 0,
            currentStage = "",
            activeAgents = 0,
            waitingAgents = 0,
            generatedCount = 0,
            passedFiltersCount = 0,
            status = "",
            lastEvent = "",
            updatedAt = "",
            fetchedAt = 123L
        )
        dao.insert(entity)
        val found = dao.getById("CAMP-1")
        assertEquals("CAMP-1", found?.id)
    }
}
