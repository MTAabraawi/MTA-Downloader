package com.example.data.extractor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HtmlMediaDocumentParserTest {
    @Test
    fun parsesMetadataRegardlessOfAttributeOrderAndDecodesEntities() {
        val html = """
            <html><head>
              <meta content="A &amp; B" property="og:title">
              <meta content="../thumb.jpg" name="twitter:image">
            </head><body>
              <video><source type="video/mp4" src="/media/clip.mp4"></video>
            </body></html>
        """.trimIndent()

        val parsed = HtmlMediaDocumentParser.parse(html, "https://media.example/watch/1")

        assertEquals("A & B", parsed.title)
        assertEquals("https://media.example/thumb.jpg", parsed.thumbnailUrl)
        assertEquals(listOf("https://media.example/media/clip.mp4"), parsed.streamUrls)
    }

    @Test
    fun safelyReturnsEmptyStreamsWhenPageHasNoVideo() {
        val parsed = HtmlMediaDocumentParser.parse("<html><title>Article</title></html>", "https://example.com/")
        assertEquals("Article", parsed.title)
        assertTrue(parsed.streamUrls.isEmpty())
    }
}
