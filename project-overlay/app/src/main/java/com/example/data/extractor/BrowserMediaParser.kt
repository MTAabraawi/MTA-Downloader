package com.example.data.extractor

import java.net.InetAddress
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
 * Literal private/reserved IP hosts are rejected before they can be handed to a downloader.
 */
object BrowserMediaParser {
    fun parse(rawUrl: String, contentType: String? = null): BrowserMediaReference? {
        val uri = runCatching { URI(rawUrl.trim()) }.getOrNull() ?: return null
        val scheme = uri.scheme?.lowercase(Locale.ROOT)
        val host = uri.host?.lowercase(Locale.ROOT)?.trimEnd('.') ?: return null
        if (scheme != "https" || uri.userInfo != null || host.isBlank() || isUnsafeHost(host)) return null

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

    private fun isUnsafeHost(rawHost: String): Boolean {
        val host = rawHost.removePrefix("[").removeSuffix("]")
        if (host == "localhost" || host.endsWith(".localhost") || host.endsWith(".local")) return true

        if (host.contains(':')) {
            val address = runCatching { InetAddress.getByName(host) }.getOrNull() ?: return true
            val bytes = address.address
            val mappedIpv4 = bytes.size == 16 && bytes.take(10).all { it == 0.toByte() } &&
                bytes[10] == 0xff.toByte() && bytes[11] == 0xff.toByte()
            if (mappedIpv4) return isUnsafeIpv4(bytes.takeLast(4).map { it.toInt() and 0xff })
            if (address.isAnyLocalAddress || address.isLoopbackAddress || address.isLinkLocalAddress ||
                address.isSiteLocalAddress || address.isMulticastAddress) return true
            // IPv6 unique-local fc00::/7 is not covered consistently by all Android API levels.
            if (bytes.isNotEmpty() && (bytes[0].toInt() and 0xfe) == 0xfc) return true
            return false
        }

        if (host.all { it.isDigit() || it == '.' }) {
            val octets = host.split('.').mapNotNull { it.toIntOrNull() }
            if (octets.size != 4 || octets.any { it !in 0..255 }) return true
            return isUnsafeIpv4(octets)
        }
        return false
    }

    private fun isUnsafeIpv4(octets: List<Int>): Boolean {
        if (octets.size != 4) return true
        val (a, b, c) = octets
        return a == 0 || a == 10 || a == 127 || a >= 224 ||
            (a == 100 && b in 64..127) ||
            (a == 169 && b == 254) ||
            (a == 172 && b in 16..31) ||
            (a == 192 && (b == 168 || (b == 0 && c in 0..2))) ||
            (a == 198 && b in 18..19) ||
            (a == 198 && b == 51 && c == 100) ||
            (a == 203 && b == 0 && c == 113)
    }
}
