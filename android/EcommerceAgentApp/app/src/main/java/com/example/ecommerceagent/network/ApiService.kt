package com.example.ecommerceagent.network

import retrofit2.http.Body
import retrofit2.http.POST

interface ApiService {
    @POST("run_task")
    suspend fun runTask(@Body request: TaskRequest): TaskResponse
}