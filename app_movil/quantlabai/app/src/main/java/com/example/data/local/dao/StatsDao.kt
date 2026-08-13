package com.example.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.data.local.StatsEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface StatsDao {

    @Query("SELECT * FROM stats ORDER BY fetchedAt DESC LIMIT 1")
    suspend fun getLatest(): StatsEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(stats: StatsEntity)

    @Query("DELETE FROM stats WHERE fetchedAt < :before")
    suspend fun deleteOlderThan(before: Long)
}
