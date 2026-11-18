package com.example.data.extractor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class BrowserMediaParserTest {
    @Test
    fun classifiesDirectVideoAndAudioFiles() {
        assertEquals(
            BrowserMediaKind.VIDEO_FILE,
            BrowserMediaParser.parse("https://cdn.example/video.mp4")?.kind
        )
        assertEquals(
            BrowserMediaKind.AUDIO_FILE,
            BrowserMediaParser.parse("https://cdn.example/audio.m4a")?.kind
        )
        assertEquals(
            BrowserMediaKind.AUDIO_FILE,
            BrowserMediaParser.parse("https://cdn.example/audio.opus")?.kind
        )
        assertEquals(
            BrowserMediaKind.VIDEO_FILE,
            BrowserMediaParser.parse("https://cdn.example/video.mkv")?.kind
        )
    }

    @Test
    fun classifiesHlsAndDashAsManifests() {
        assertEquals(
            BrowserMediaKind.HLS_MANIFEST,
            BrowserMediaParser.parse("https://cdn.example/master.m3u8")?.kind
        )
        assertEquals(
            BrowserMediaKind.DASH_MANIFEST,
            BrowserMediaParser.parse("https://cdn.example/manifest", "application/dash+xml")?.kind
        )
    }

    @Test
    fun rejectsUnsafeOrUnsupportedUrls() {
        assertNull(BrowserMediaParser.parse("http://cdn.example/video.mp4"))
        assertNull(BrowserMediaParser.parse("https://user:pass@cdn.example/video.mp4"))
        assertNull(BrowserMediaParser.parse("https://localhost/video.mp4"))
        assertNull(BrowserMediaParser.parse("https://172.16.0.8/video.mp4"))
        assertNull(BrowserMediaParser.parse("https://100.64.0.1/video.mp4"))
        assertNull(BrowserMediaParser.parse("https://[::1]/video.mp4"))
        assertNull(BrowserMediaParser.parse("https://[fd00::1]/video.mp4"))
        assertNull(BrowserMediaParser.parse("https://cdn.example/page"))
    }
}
