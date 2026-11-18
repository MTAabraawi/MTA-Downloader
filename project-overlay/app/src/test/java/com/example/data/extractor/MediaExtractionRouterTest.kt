package com.example.data.extractor

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MediaExtractionRouterTest {
    @Test
    fun firstSuccessfulProviderStopsFallbackChain() = runBlocking {
        val calls = mutableListOf<String>()
        val result = MediaExtractionRouter.firstAvailable(
            { calls += "newpipe"; "native-result" },
            { calls += "html"; "html-result" },
            { calls += "ytdlp"; "ytdlp-result" }
        )
        assertEquals("native-result", result)
        assertEquals(listOf("newpipe"), calls)
    }

    @Test
    fun nullAndOrdinaryProviderFailureContinueToHtmlParser() = runBlocking {
        val calls = mutableListOf<String>()
        val result = MediaExtractionRouter.firstAvailable<String>(
            { calls += "newpipe"; null },
            { calls += "html"; throw IllegalStateException("fixture failure") }
        )
        assertNull(result)
        assertEquals(listOf("newpipe", "html"), calls)
    }

    @Test
    fun allProvidersUnsupportedReturnsNull() = runBlocking {
        val result = MediaExtractionRouter.firstAvailable<String>(
            { null },
            { null }
        )
        assertNull(result)
    }

    @Test
    fun cancellationIsNotSwallowedByFallbackRouter() {
        var cancellationPropagated = false
        try {
            runBlocking {
                MediaExtractionRouter.firstAvailable<String>(
                    { throw CancellationException("cancel test") },
                    { "must-not-run" }
                )
            }
        } catch (_: CancellationException) {
            cancellationPropagated = true
        }
        assertEquals(true, cancellationPropagated)
    }
}
