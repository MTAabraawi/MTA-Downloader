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
    fun nullAndOrdinaryProviderFailureContinueToNextEngine() = runBlocking {
        val calls = mutableListOf<String>()
        val result = MediaExtractionRouter.firstAvailable<String>(
            { calls += "newpipe"; null },
            { calls += "html"; throw IllegalStateException("fixture failure") },
            { calls += "ytdlp"; "fallback-result" }
        )
        assertEquals("fallback-result", result)
        assertEquals(listOf("newpipe", "html", "ytdlp"), calls)
    }

    @Test
    fun allProvidersUnsupportedReturnsNull() = runBlocking {
        val result = MediaExtractionRouter.firstAvailable<String>(
            { null },
            { null },
            { null }
        )
        assertNull(result)
    }

    @Test(expected = CancellationException::class)
    fun cancellationIsNotSwallowedByFallbackRouter() = runBlocking {
        MediaExtractionRouter.firstAvailable<String>(
            { throw CancellationException("cancel test") },
            { "must-not-run" }
        )
    }
}
