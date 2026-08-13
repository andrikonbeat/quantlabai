package com.example.data.remote.model

import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class ApiModelsTest {

    private val moshi: Moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    @Test
    fun `ApiHealth parses from JSON`() {
        val json = """{"success":true,"data":{"status":"ok","version":"0.1.0"}}"""
        val type = Types.newParameterizedType(ApiEnvelope::class.java, ApiHealth::class.java)
        val adapter = moshi.adapter<ApiEnvelope<ApiHealth>>(type)
        val envelope = adapter.fromJson(json)
        assertNotNull(envelope)
        val health = envelope?.data
        assertNotNull(health)
        assertEquals(true, envelope?.success)
        assertEquals("ok", health?.status)
        assertEquals("0.1.0", health?.version)
    }

    @Test
    fun `ApiCampaign parses snake_case fields`() {
        val json = """{"success":true,"data":[{"campaign_id":"CAMP-027","name":"Test","market":"EURUSD","timeframe":"H1","sharpe":2.15,"profit_factor":1.92,"win_rate":0.58,"status":"ACTIVE","total_return":14280.0,"metrics":null,"tags":[],"created":"2025-01-01","path":"/test"}]}"""
        val listType = Types.newParameterizedType(List::class.java, ApiCampaign::class.java)
        val envelopeType = Types.newParameterizedType(ApiEnvelope::class.java, listType)
        val adapter = moshi.adapter<ApiEnvelope<List<ApiCampaign>>>(envelopeType)
        val envelope = adapter.fromJson(json)
        assertNotNull(envelope)
        val campaign = envelope?.data?.firstOrNull()
        assertNotNull(campaign)
        assertEquals("CAMP-027", campaign?.campaignId)
        assertEquals("EURUSD", campaign?.market)
        assertEquals(2.15, campaign?.sharpe ?: 0.0, 0.001)
    }

    @Test
    fun `ApiStats parses all fields`() {
        val json = """{"success":true,"data":{"sharpe_mean":1.85,"sharpe_std":0.42,"max_drawdown_pct":8.5,"win_rate_mean":0.55,"total_trades":1200,"benchmark_comparison":null,"total_campaigns":5,"total_pipeline_runs":3,"generated_at":"2025-01-01T00:00:00Z"}}"""
        val type = Types.newParameterizedType(ApiEnvelope::class.java, ApiStats::class.java)
        val adapter = moshi.adapter<ApiEnvelope<ApiStats>>(type)
        val envelope = adapter.fromJson(json)
        assertNotNull(envelope)
        val stats = envelope?.data
        assertNotNull(stats)
        assertEquals(1.85, stats?.sharpeMean ?: 0.0, 0.001)
        assertEquals(5, stats?.totalCampaigns)
    }

    @Test
    fun `ApiCampaignDetail parses nested fields`() {
        val json = """{"success":true,"data":{"campaign_id":"CAMP-027","name":"Test","market":"EURUSD","timeframe":"H1","sharpe":null,"profit_factor":null,"win_rate":null,"status":"ACTIVE","total_return":null,"metrics":null,"tags":null,"created":null,"path":null,"equity_curve":[],"trades":[],"statistics":{},"phases":[]}}"""
        val type = Types.newParameterizedType(ApiEnvelope::class.java, ApiCampaignDetail::class.java)
        val adapter = moshi.adapter<ApiEnvelope<ApiCampaignDetail>>(type)
        val envelope = adapter.fromJson(json)
        assertNotNull(envelope)
        val detail = envelope?.data
        assertNotNull(detail)
        assertEquals("CAMP-027", detail?.campaignId)
        assertEquals(0, detail?.equityCurve?.size)
    }
}
