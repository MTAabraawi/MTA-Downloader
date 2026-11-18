package com.example.data.extractor

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertNull
import org.junit.Test

class NewPipeMediaProviderTest {
    @Test
    fun unsupportedServiceReturnsNullForTheNextFallbackProvider() = runBlocking {
        val result = NewPipeMediaProvider.extract(
            url = "https://media.example.invalid/watch/12345",
            customTitle = null,
            fallbackPlatform = "Example"
        )
        assertNull(result)
    }
}
