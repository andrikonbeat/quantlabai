package com.example.data.remote

import com.example.data.remote.model.ApiCampaign
import com.example.data.remote.model.ApiCampaignDetail
import com.example.data.remote.model.ApiEnvelope
import com.example.data.remote.model.ApiHealth
import com.example.data.remote.model.ApiPipelineRun
import com.example.data.remote.model.ApiStats
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path

interface ApiService {

    @GET("api/health")
    suspend fun getHealth(): Response<ApiEnvelope<ApiHealth>>

    @GET("api/campaigns")
    suspend fun getCampaigns(): Response<ApiEnvelope<List<ApiCampaign>>>

    @GET("api/campaigns/{id}")
    suspend fun getCampaign(@Path("id") id: String): Response<ApiEnvelope<ApiCampaignDetail>>

    @GET("api/pipeline")
    suspend fun getPipelineRuns(): Response<ApiEnvelope<List<ApiPipelineRun>>>

    @GET("api/stats")
    suspend fun getStats(): Response<ApiEnvelope<ApiStats>>
}
