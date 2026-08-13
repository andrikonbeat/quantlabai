package com.example.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.data.local.CampaignEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface CampaignDao {

    @Query("SELECT * FROM campaigns ORDER BY fetchedAt DESC")
    fun getAll(): Flow<List<CampaignEntity>>

    @Query("SELECT * FROM campaigns WHERE id = :id ORDER BY fetchedAt DESC LIMIT 1")
    suspend fun getById(id: String): CampaignEntity?

    @Query("SELECT * FROM campaigns ORDER BY fetchedAt DESC LIMIT 1")
    suspend fun getLatest(): CampaignEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(campaigns: List<CampaignEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(campaign: CampaignEntity)

    @Query("DELETE FROM campaigns WHERE fetchedAt < :before")
    suspend fun deleteOlderThan(before: Long)

    @Delete
    suspend fun delete(campaign: CampaignEntity)
}
