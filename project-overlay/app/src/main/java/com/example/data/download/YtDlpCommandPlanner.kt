package com.example.data.download

import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

internal object YtDlpCommandPlanner {
    fun isPlaylistUrl(rawUrl: String): Boolean {
        val uri = runCatching { URI(rawUrl) }.getOrNull() ?: return false
        val path = uri.path.orEmpty()
        val hasPlaylistId = uri.rawQuery.orEmpty().split('&').any { part ->
            val key = runCatching {
                URLDecoder.decode(part.substringBefore('='), StandardCharsets.UTF_8.name())
            }.getOrNull()
            val value = part.substringAfter('=', "")
            key.equals("list", ignoreCase = true) && value.isNotBlank()
        }
        return hasPlaylistId ||
            path.contains("/playlist", ignoreCase = true) ||
            path.contains("/showcase/", ignoreCase = true)
    }

    fun formatSelector(qualityId: String, mimeType: String): String = when {
        qualityId == "subtitles" -> "best"
        qualityId.contains("1080") -> "best[height<=1080]/best"
        qualityId.contains("720") -> "best[height<=720]/best"
        qualityId.contains("480") -> "best[height<=480]/best"
        qualityId.contains("360") -> "best[height<=360]/best"
        qualityId.equals("m4a", true) || mimeType.startsWith("audio/") ->
            "bestaudio[ext=m4a]/bestaudio"
        else -> "best"
    }

    /** Each pair is an option and its optional value; null means a flag-only option. */
    fun buildOptions(qualityId: String, mimeType: String, playlist: Boolean): List<Pair<String, String?>> {
        val options = mutableListOf(
            (if (playlist) "--yes-playlist" else "--no-playlist") to null,
            "--no-warnings" to null,
            "--newline" to null,
            "-f" to formatSelector(qualityId, mimeType)
        )
        if (qualityId == "subtitles") {
            options += listOf(
                "--skip-download" to null,
                "--write-subs" to null,
                "--write-auto-subs" to null,
                "--sub-langs" to "all",
                "--sub-format" to "vtt/best"
            )
        }
        return options
    }
}
