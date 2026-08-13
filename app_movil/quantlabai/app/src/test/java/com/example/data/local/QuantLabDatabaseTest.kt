package com.example.data.local

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class QuantLabDatabaseTest {

    @Test
    fun `database can be built with fallbackToDestructiveMigration false`() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val db = Room.inMemoryDatabaseBuilder(context, QuantLabDatabase::class.java)
            .fallbackToDestructiveMigration(false)
            .build()
        assertNotNull(db)
        db.close()
    }
}
