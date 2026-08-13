package com.example.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.data.local.HealthEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface HealthDao {

    @Query("SELECT * FROM health ORDER BY fetchedAt DESC LIMIT 1")
    suspend fun getLatest(): HealthEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(health: HealthEntity)

    @Query("DELETE FROM health WHERE fetchedAt < :before")
    suspend fun deleteOlderThan(before: Long)
}
