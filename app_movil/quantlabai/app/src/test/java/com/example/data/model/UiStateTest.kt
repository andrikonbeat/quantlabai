package com.example.data.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class UiStateTest {

    @Test
    fun `Loading has no data`() {
        val state = UiState.Loading
        assertTrue(state is UiState.Loading)
    }

    @Test
    fun `Success wraps data`() {
        val state = UiState.Success("hello")
        assertEquals("hello", (state as UiState.Success<String>).data)
    }

    @Test
    fun `Error wraps message`() {
        val state = UiState.Error("oops")
        assertEquals("oops", (state as UiState.Error).message)
    }
}
