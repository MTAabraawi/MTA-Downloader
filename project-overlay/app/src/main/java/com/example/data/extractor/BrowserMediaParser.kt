package com.example.data.extractor

import java.net.URI
import java.util.Locale

enum class BrowserMediaKind {
    VIDEO_FILE,
    AUDIO_FILE,
    HLS_MANIFEST,
    DASH_MANIFEST
}

data class BrowserMediaReference(
    val url: String,
    val kind: BrowserMediaKind,
    val mimeType: String
)

/**
 * Classifies public media URLs observed during the user's own browser session.
 * HLS/DASH are manifests, not MP4 files; they are routed to an extractor/remux-capable path.
 */
object BrowserMediaParser {
    fun parse(rawUrl: String, contentType: String? = null): BrowserMediaReference? {
        val uri = runCatching { URI(rawUrl.trim()) }.getOrNull() ?: return null
        val scheme = uri.scheme?.lowercase(Locale.ROOT)
        val host = uri.host?.lowercase(Locale.ROOT)?.trimEnd('.') ?: return null
        if (scheme != "https" || uri.userInfo != null || host.isBlank()) return null
        if (host == "localhost" || host.endsWith(".localhost") || host.endsWith(".local")) return null
        if (host == "0.0.0.0" || host == "127.0.0.1" || host.startsWith("10.") ||
            host.startsWith("192.168.") || host.startsWith("169.254.")) return null

        val path = uri.path.orEmpty().lowercase(Locale.ROOT)
        val mime = contentType.orEmpty().substringBefore(';').trim().lowercase(Locale.ROOT)
        val kind = when {
            path.endsWith(".m3u8") || mime.contains("mpegurl") || mime == "application/x-mpegurl" ->
                BrowserMediaKind.HLS_MANIFEST
            path.endsWith(".mpd") || mime == "application/dash+xml" ->
                BrowserMediaKind.DASH_MANIFEST
            path.endsWith(".mp3") || path.endsWith(".m4a") || path.endsWith(".aac") ||
                path.endsWith(".wav") || path.endsWith(".ogg") || path.endsWith(".opus") ||
                mime.startsWith("audio/") -> BrowserMediaKind.AUDIO_FILE
            path.endsWith(".mp4") || path.endsWith(".m4v") || path.endsWith(".webm") ||
                path.endsWith(".mov") || mime.startsWith("video/") -> BrowserMediaKind.VIDEO_FILE
            else -> return null
        }
        val normalizedMime = when (kind) {
            BrowserMediaKind.HLS_MANIFEST -> "application/vnd.apple.mpegurl"
            BrowserMediaKind.DASH_MANIFEST -> "application/dash+xml"
            BrowserMediaKind.AUDIO_FILE -> mime.ifBlank { "audio/*" }
            BrowserMediaKind.VIDEO_FILE -> mime.ifBlank { "video/*" }
        }
        return BrowserMediaReference(uri.toASCIIString(), kind, normalizedMime)
    }
}
