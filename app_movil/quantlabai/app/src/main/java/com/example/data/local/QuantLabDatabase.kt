package com.example.data.local

import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import com.example.data.local.dao.CampaignDao
import com.example.data.local.dao.HealthDao
import com.example.data.local.dao.PipelineDao
import com.example.data.local.dao.StatsDao

@Database(
    entities = [
        CampaignEntity::class,
        PipelineRunEntity::class,
        StatsEntity::class,
        HealthEntity::class
    ],
    version = 1,
    exportSchema = false
)
abstract class QuantLabDatabase : RoomDatabase() {
    abstract fun campaignDao(): CampaignDao
    abstract fun pipelineDao(): PipelineDao
    abstract fun statsDao(): StatsDao
    abstract fun healthDao(): HealthDao

    companion object {
        @Volatile
        private var INSTANCE: QuantLabDatabase? = null

        fun getInstance(context: android.content.Context): QuantLabDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    QuantLabDatabase::class.java,
                    "quantlab_database"
                )
                    .fallbackToDestructiveMigration(false)
                    .build()
                    .also { INSTANCE = it }
            }
        }
    }
}
