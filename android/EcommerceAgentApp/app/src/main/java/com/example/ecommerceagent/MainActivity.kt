package com.example.ecommerceagent

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.ecommerceagent.network.RetrofitClient
import com.example.ecommerceagent.network.StepTrace
import com.example.ecommerceagent.network.TaskRequest
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                EcommerceAgentApp()
            }
        }
    }
}

@Composable
fun EcommerceAgentApp() {
    var userInput by remember {
        mutableStateOf("帮我查一下订单1001的物流，并判断现在还能不能改地址")
    }
    var finalAnswer by remember { mutableStateOf("") }
    var steps by remember { mutableStateOf<List<StepTrace>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var errorText by remember { mutableStateOf("") }

    val scope = rememberCoroutineScope()

    Scaffold(
        modifier = Modifier.fillMaxSize()
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                Text(
                    text = "E-commerce Agent Demo",
                    style = MaterialTheme.typography.headlineMedium
                )
            }

            item {
                OutlinedTextField(
                    value = userInput,
                    onValueChange = { userInput = it },
                    label = { Text("请输入任务") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("task_input")
                )
            }

            item {
                Button(
                    onClick = {
                        errorText = ""
                        finalAnswer = ""
                        steps = emptyList()
                        loading = true

                        scope.launch {
                            try {
                                val response = RetrofitClient.apiService.runTask(
                                    TaskRequest(user_input = userInput)
                                )
                                finalAnswer = response.final_answer
                                steps = response.steps
                            } catch (e: Exception) {
                                errorText = e.message ?: "请求失败"
                            } finally {
                                loading = false
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("run_button")
                ) {
                    Text("调用云端 Agent")
                }
            }

            if (loading) {
                item {
                    CircularProgressIndicator()
                }
            }

            if (errorText.isNotBlank()) {
                item {
                    Card {
                        Text(
                            text = "错误：$errorText",
                            modifier = Modifier.padding(16.dp)
                        )
                    }
                }
            }

            if (finalAnswer.isNotBlank()) {
                item {
                    Card(
                        modifier = Modifier.testTag("final_answer_card")
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text(
                                text = "最终回答",
                                style = MaterialTheme.typography.titleMedium
                            )
                            Text(
                                text = finalAnswer,
                                modifier = Modifier.padding(top = 8.dp)
                            )
                        }
                    }
                }
            }

            if (steps.isNotEmpty()) {
                item {
                    Text(
                        text = "执行步骤",
                        style = MaterialTheme.typography.titleMedium
                    )
                }

                items(steps) { step ->
                    StepCard(step)
                }
            }
        }
    }
}

@Composable
fun StepCard(step: StepTrace) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Step ${step.step}",
                style = MaterialTheme.typography.titleSmall
            )

            Text(
                text = "Thought: ${step.thought}",
                modifier = Modifier.padding(top = 8.dp)
            )

            Text(
                text = "Action: ${step.action}",
                modifier = Modifier.padding(top = 6.dp)
            )

            Text(
                text = "Summary: ${buildStepSummary(step)}",
                modifier = Modifier.padding(top = 6.dp)
            )
        }
    }
}

fun buildStepSummary(step: StepTrace): String {
    val observation = step.observation ?: return "无返回结果"

    return when (step.action) {
        "query_logistics" -> {
            val data = observation["data"] as? Map<*, *>
            val status = data?.get("status")?.toString() ?: "未知状态"
            val trackingNo = data?.get("tracking_no")?.toString() ?: "无运单号"
            "物流状态：$status，运单号：$trackingNo"
        }

        "query_kb" -> {
            val data = observation["data"] as? Map<*, *>
            val results = data?.get("results") as? List<*>
            val firstResult = results?.firstOrNull() as? Map<*, *>

            val title = firstResult?.get("title")?.toString() ?: "未命中规则"
            val evidence = firstResult?.get("evidence")?.toString() ?: "无证据摘要"

            "命中规则：$title；证据：$evidence"
        }

        "modify_order" -> {
            val data = observation["data"] as? Map<*, *>
            val newAddress = data?.get("new_address")?.toString() ?: "未知地址"
            "订单地址已更新为：$newAddress"
        }

        else -> {
            summarizeGenericObservation(observation)
        }
    }
}

fun summarizeGenericObservation(observation: Map<String, Any?>): String {
    val success = observation["success"]?.toString() ?: "unknown"
    val error = observation["error"]?.toString()

    return if (success == "true") {
        "执行成功"
    } else {
        "执行失败：${error ?: "未知错误"}"
    }
}