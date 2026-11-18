package com.example.data.download

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SegmentedHttpDownloaderTest {
    private val downloader = SegmentedHttpDownloader()

    @Test
    fun parsesValidContentRange() {
        assertEquals(Triple(0L, 0L, 1024L), downloader.parseContentRange("bytes 0-0/1024"))
        assertEquals(Triple(100L, 199L, 1024L), downloader.parseContentRange("bytes 100-199/1024"))
    }

    @Test
    fun rejectsMalformedContentRange() {
        assertNull(downloader.parseContentRange(null))
        assertNull(downloader.parseContentRange("bytes 199-100/1024"))
        assertNull(downloader.parseContentRange("bytes 0-1024/1024"))
        assertNull(downloader.parseContentRange("items 0-1/2"))
    }
}
