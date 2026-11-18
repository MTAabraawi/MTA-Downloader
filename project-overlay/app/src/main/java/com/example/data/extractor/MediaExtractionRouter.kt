package com.example.data.extractor

import com.example.data.model.VideoItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.util.concurrent.ConcurrentHashMap

/**
 * Coordinates native extraction with bounded execution and short-lived URL de-duplication.
 * The caller retains the existing HTML and yt-dlp fallbacks when this router returns null.
 */
internal object MediaExtractionRouter {
    private data class CachedResult(val createdAt: Long, val item: VideoItem)

    private const val CACHE_TTL_MS = 90_000L
    private const val EXTRACTION_TIMEOUT_MS = 75_000L
    private val locks = ConcurrentHashMap<String, Mutex>()
    private val cache = ConcurrentHashMap<String, CachedResult>()

    suspend fun extract(
        url: String,
        customTitle: String?,
        platform: String
    ): VideoItem? = withContext(Dispatchers.IO) {
        val key = url.trim()
        val mutex = locks.getOrPut(key) { Mutex() }
        try {
            mutex.withLock {
                val now = System.currentTimeMillis()
                cache[key]?.takeIf { now - it.createdAt <= CACHE_TTL_MS }?.let {
                    return@withLock it.item
                }
                val extracted = withTimeoutOrNull(EXTRACTION_TIMEOUT_MS) {
                    NewPipeMediaProvider.extract(key, customTitle, platform)
                }
                if (extracted != null) {
                    cache[key] = CachedResult(System.currentTimeMillis(), extracted)
                }
                extracted
            }
        } finally {
            if (!mutex.isLocked) locks.remove(key, mutex)
            val cutoff = System.currentTimeMillis() - CACHE_TTL_MS
            cache.entries.removeAll { it.value.createdAt < cutoff }
        }
    }

    fun classifyBrowserMedia(url: String, contentType: String? = null): BrowserMediaReference? =
        BrowserMediaParser.parse(url, contentType)
}
