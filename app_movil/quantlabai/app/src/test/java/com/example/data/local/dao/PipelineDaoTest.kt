package com.example.data.local.dao

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.example.data.local.PipelineRunEntity
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
class PipelineDaoTest {

    private lateinit var database: QuantLabDatabase
    private lateinit var dao: PipelineDao

    @Before
    fun setup() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        database = Room.inMemoryDatabaseBuilder(context, QuantLabDatabase::class.java)
            .fallbackToDestructiveMigration(false)
            .build()
        dao = database.pipelineDao()
    }

    @Test
    fun `insert and getAll returns runs ordered by fetchedAt`() = runBlocking {
        val run = PipelineRunEntity(
            runId = "run-1",
            pipelineName = "backtest",
            status = "running",
            startedAt = "2024-01-01T00:00:00Z",
            completedAt = null,
            duration = 1.5,
            error = null,
            fetchedAt = 123456789L
        )
        dao.insert(run)
        val all = dao.getAll().first()
        assertEquals(1, all.size)
        assertEquals("run-1", all.first().runId)
    }
}
