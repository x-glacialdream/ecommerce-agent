package com.example.ecommerceagent.network

data class TaskRequest(
    val user_input: String
)

data class TaskResponse(
    val status: String,
    val final_answer: String,
    val steps: List<StepTrace>,
    val stop_reason: String
)

data class StepTrace(
    val step: Int,
    val thought: String,
    val action: String,
    val action_input: Map<String, Any?>,
    val observation: Map<String, Any?>?
)