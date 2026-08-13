package com.example.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.data.local.PipelineRunEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PipelineDao {

    @Query("SELECT * FROM pipeline_runs ORDER BY fetchedAt DESC")
    fun getAll(): Flow<List<PipelineRunEntity>>

    @Query("SELECT * FROM pipeline_runs WHERE runId = :runId ORDER BY fetchedAt DESC LIMIT 1")
    suspend fun getById(runId: String): PipelineRunEntity?

    @Query("SELECT * FROM pipeline_runs ORDER BY fetchedAt DESC LIMIT 1")
    suspend fun getLatest(): PipelineRunEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(runs: List<PipelineRunEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(run: PipelineRunEntity)

    @Query("DELETE FROM pipeline_runs WHERE fetchedAt < :before")
    suspend fun deleteOlderThan(before: Long)
}
