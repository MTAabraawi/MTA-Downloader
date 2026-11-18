package com.example.data.download

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class YtDlpOutputCollectorTest {
    @Test
    fun collectsEveryRecentPlaylistVideoAndSubtitleFileRecursively() {
        val root = Files.createTempDirectory("mta-ytdlp-output").toFile()
        try {
            val startedAt = System.currentTimeMillis()
            val playlist = File(root, "Playlist")
            val nested = File(playlist, "subtitles")
            assertTrue(nested.mkdirs())
            val first = File(playlist, "001 - Intro [a1].mp4").apply { writeText("video-1") }
            val second = File(playlist, "002 - Lecture [a2].webm").apply { writeText("video-2") }
            val captions = File(nested, "002 - Lecture [a2].en.vtt").apply { writeText("WEBVTT") }
            val ignoredJson = File(playlist, "playlist.json").apply { writeText("{}") }
            val empty = File(playlist, "003 - Empty [a3].mp4").apply { createNewFile() }
            val stale = File(playlist, "000 - Old [a0].mp4").apply {
                writeText("old")
                setLastModified(startedAt - 30_000L)
            }

            val files = YtDlpOutputCollector.collectRecentMediaFiles(root, startedAt)

            assertEquals(listOf(first, second, captions), files)
            assertTrue(ignoredJson !in files)
            assertTrue(empty !in files)
            assertTrue(stale !in files)
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun derivesPlaylistItemTitleAndPreservesRequestedSingleVideoTitle() {
        val playlistFile = File("004 - Chapter Four [video-id].mp4")
        assertEquals(
            "Chapter Four [video-id]",
            YtDlpOutputCollector.displayTitle(playlistFile, isPlaylist = true, requestedTitle = "Playlist")
        )
        assertEquals(
            "Requested title",
            YtDlpOutputCollector.displayTitle(playlistFile, isPlaylist = false, requestedTitle = "Requested title")
        )
    }
}
