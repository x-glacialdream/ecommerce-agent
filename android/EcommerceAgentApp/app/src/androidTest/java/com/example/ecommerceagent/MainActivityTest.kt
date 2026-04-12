package com.example.ecommerceagent

import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import org.junit.Rule
import org.junit.Test

class MainActivityTest {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun inputAndRunButton_shouldExist() {
        composeTestRule.onNodeWithTag("task_input").assertExists()
        composeTestRule.onNodeWithTag("run_button").assertExists()
    }

    @Test
    fun runButton_shouldBeClickable() {
        composeTestRule.onNodeWithTag("run_button").performClick()
    }
}