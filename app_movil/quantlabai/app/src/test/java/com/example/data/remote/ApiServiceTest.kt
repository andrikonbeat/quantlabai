package com.example.data.remote

import com.example.data.remote.model.ApiEnvelope
import com.example.data.remote.model.ApiHealth
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Test
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory

class ApiServiceTest {

    private lateinit var mockWebServer: MockWebServer
    private lateinit var apiService: ApiService

    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        mockWebServer.start()

        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        apiService = Retrofit.Builder()
            .baseUrl(mockWebServer.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(ApiService::class.java)
    }

    @After
    fun teardown() {
        mockWebServer.shutdown()
    }

    @Test
    fun `getHealth returns envelope with health data`() = runBlocking {
        mockWebServer.enqueue(
            MockResponse()
                .setBody("{\"success\":true,\"data\":{\"status\":\"ok\",\"version\":\"0.1.0\"}}")
                .setResponseCode(200)
        )

        val response = apiService.getHealth()
        assertEquals(200, response.code())
        val envelope = response.body()
        assertNotNull(envelope)
        assertEquals(true, envelope?.success)
        assertEquals("ok", envelope?.data?.status)
    }

    @Test
    fun `getCampaigns returns list of campaigns`() = runBlocking {
        mockWebServer.enqueue(
            MockResponse()
                .setBody("{\"success\":true,\"data\":[{\"campaign_id\":\"CAMP-001\",\"name\":\"Test\",\"market\":\"EURUSD\",\"timeframe\":\"H1\",\"sharpe\":1.5,\"profit_factor\":1.8,\"win_rate\":0.6,\"status\":\"ACTIVE\",\"total_return\":1000.0,\"metrics\":null,\"tags\":[],\"created\":\"2025-01-01\",\"path\":\"/test\"}]}")
                .setResponseCode(200)
        )

        val response = apiService.getCampaigns()
        assertEquals(200, response.code())
        val campaigns = response.body()?.data
        assertNotNull(campaigns)
        assertEquals(1, campaigns?.size)
        assertEquals("CAMP-001", campaigns?.firstOrNull()?.campaignId)
    }

    @Test
    fun `getCampaign returns specific campaign`() = runBlocking {
        mockWebServer.enqueue(
            MockResponse()
                .setBody("{\"success\":true,\"data\":{\"campaign_id\":\"CAMP-002\",\"name\":\"Detail\",\"market\":\"GBPUSD\",\"timeframe\":\"M30\",\"sharpe\":null,\"profit_factor\":null,\"win_rate\":null,\"status\":\"PAUSED\",\"total_return\":null,\"metrics\":null,\"tags\":null,\"created\":null,\"path\":null,\"equity_curve\":[],\"trades\":[],\"statistics\":{},\"phases\":[]}}")
                .setResponseCode(200)
        )

        val response = apiService.getCampaign("CAMP-002")
        assertEquals(200, response.code())
        val detail = response.body()?.data
        assertNotNull(detail)
        assertEquals("CAMP-002", detail?.campaignId)
        assertEquals("GBPUSD", detail?.market)
    }
}
