package com.example.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "health")
data class HealthEntity(
    @PrimaryKey val status: String,
    val version: String,
    val fetchedAt: Long
)
