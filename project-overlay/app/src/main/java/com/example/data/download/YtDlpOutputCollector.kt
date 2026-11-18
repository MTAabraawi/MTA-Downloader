package com.example.data.download

import java.io.File
import java.util.Locale

internal object YtDlpOutputCollector {
    private val mediaExtensions = setOf(
        "mp4", "m4v", "webm", "mov", "mkv", "mp3", "m4a", "aac",
        "wav", "ogg", "opus", "flv", "ts", "vtt", "srt", "ttml",
        "srv1", "srv2", "srv3"
    )

    fun collectRecentMediaFiles(outputDirectory: File, startedAtMillis: Long): List<File> =
        outputDirectory.walkTopDown()
            .filter { file ->
                file.isFile &&
                    file.length() > 0L &&
                    file.lastModified() >= startedAtMillis - 2_000L &&
                    file.extension.lowercase(Locale.ROOT) in mediaExtensions
            }
            .sortedBy(File::lastModified)
            .toList()

    fun displayTitle(file: File, isPlaylist: Boolean, requestedTitle: String): String =
        if (isPlaylist) {
            file.nameWithoutExtension.substringAfter(" - ", file.nameWithoutExtension)
        } else {
            requestedTitle
        }
}
