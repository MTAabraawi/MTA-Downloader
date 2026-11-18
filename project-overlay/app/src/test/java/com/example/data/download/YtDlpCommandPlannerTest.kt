package com.example.data.download

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class YtDlpCommandPlannerTest {
    @Test
    fun recognizesPlaylistQueryAndPathVariants() {
        assertTrue(YtDlpCommandPlanner.isPlaylistUrl("https://www.youtube.com/watch?v=abc&list=PL123"))
        assertTrue(YtDlpCommandPlanner.isPlaylistUrl("https://example.com/playlist/42"))
        assertTrue(YtDlpCommandPlanner.isPlaylistUrl("https://vimeo.com/showcase/123"))
        assertFalse(YtDlpCommandPlanner.isPlaylistUrl("https://www.youtube.com/watch?v=abc"))
        assertFalse(YtDlpCommandPlanner.isPlaylistUrl("not a url"))
    }

    @Test
    fun subtitlePlanRequestsManualAndAutomaticCaptionsWithoutMediaDownload() {
        val options = YtDlpCommandPlanner.buildOptions("subtitles", "text/vtt", playlist = false)
        val flags = options.map { it.first }
        assertTrue(flags.contains("--skip-download"))
        assertTrue(flags.contains("--write-subs"))
        assertTrue(flags.contains("--write-auto-subs"))
        assertEquals("all", options.first { it.first == "--sub-langs" }.second)
        assertEquals("vtt/best", options.first { it.first == "--sub-format" }.second)
        assertFalse(flags.contains("--yes-playlist"))
        assertTrue(flags.contains("--no-playlist"))
    }

    @Test
    fun playlistAndQualityOptionsArePreserved() {
        val options = YtDlpCommandPlanner.buildOptions("720p", "video/mp4", playlist = true)
        assertTrue(options.contains("--yes-playlist" to null))
        assertTrue(options.contains("-f" to "best[height<=720]/best"))
        assertFalse(options.any { it.first.startsWith("--write-") })
    }

    @Test
    fun audioSelectionUsesAudioOnlyFormatSelector() {
        assertEquals(
            "bestaudio[ext=m4a]/bestaudio",
            YtDlpCommandPlanner.formatSelector("m4a", "audio/mp4")
        )
    }
}
