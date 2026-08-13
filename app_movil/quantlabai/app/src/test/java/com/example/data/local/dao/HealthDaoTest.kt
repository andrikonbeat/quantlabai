package com.example.data.local.dao

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.example.data.local.HealthEntity
import com.example.data.local.QuantLabDatabase
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class HealthDaoTest {

    private lateinit var database: QuantLabDatabase
    private lateinit var dao: HealthDao

    @Before
    fun setup() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        database = Room.inMemoryDatabaseBuilder(context, QuantLabDatabase::class.java)
            .fallbackToDestructiveMigration(false)
            .build()
        dao = database.healthDao()
    }

    @Test
    fun `insert and getLatest returns health`() = runBlocking {
        val entity = HealthEntity(
            status = "ok",
            version = "1.0.0",
            fetchedAt = 123456789L
        )
        dao.insert(entity)
        val latest = dao.getLatest()
        assertEquals("ok", latest?.status)
    }
}
