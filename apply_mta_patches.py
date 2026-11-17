from pathlib import Path
import re

root = Path("project")

def edit(path, old, new, label):
    p = root / path
    s = p.read_text()
    if new in s:
        return
    if old not in s:
        raise SystemExit(f"Patch anchor missing: {label} in {path}")
    p.write_text(s.replace(old, new, 1))

edit("app/src/main/java/com/example/MainActivity.kt", """    private fun handleIncomingShareIntent(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND && intent.type == "text/plain") {
            val sharedText = intent.getStringExtra(Intent.EXTRA_TEXT)
            if (!sharedText.isNullOrBlank() && ::mainViewModel.isInitialized) {
                mainViewModel.handleSharedTextFromExternalApp(sharedText)
            }
        }
    }
""", """    private fun handleIncomingShareIntent(intent: Intent?) {
        if (!::mainViewModel.isInitialized || intent == null) return

        val sharedText = when (intent.action) {
            Intent.ACTION_SEND -> intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString()
            Intent.ACTION_VIEW -> intent.dataString
            else -> null
        }

        if (!sharedText.isNullOrBlank()) {
            mainViewModel.handleSharedTextFromExternalApp(sharedText)
        }
    }
""", "Android incoming links")

manifest = root / "app/src/main/AndroidManifest.xml"
s = manifest.read_text()
anchor = """            <intent-filter>
                <action android:name="android.intent.action.SEND" />
                <category android:name="android.intent.category.DEFAULT" />
                <data android:mimeType="text/plain" />
            </intent-filter>
"""
replacement = anchor + """
            <!-- Open supported web links directly in MTA Downloader -->
            <intent-filter android:autoVerify="false">
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="http" />
                <data android:scheme="https" />
            </intent-filter>
"""
if replacement not in s:
    if anchor not in s:
        raise SystemExit("Patch anchor missing: manifest VIEW filter")
    manifest.write_text(s.replace(anchor, replacement, 1))

edit("app/src/main/java/com/example/data/model/VideoModels.kt", """    val mimeType: String,
    val overrideStreamUrl: String? = null
)""", """    val mimeType: String,
    val overrideStreamUrl: String? = null,
    val requestHeaders: Map<String, String> = emptyMap()
)""", "quality request headers")

edit("app/src/main/java/com/example/data/repository/DownloadRepository.kt", """            val fileName = "${sanitizedName}_${quality.id}.${quality.extension}"

            val dmRequest = DownloadManager.Request(Uri.parse(targetStreamUrl)).apply {
                setTitle(request.title)
""", """            val safeExtension = quality.extension.lowercase().filter { it.isLetterOrDigit() }.take(8).ifBlank { "mp4" }
            val safeQualityId = quality.id.replace(Regex("[^a-zA-Z0-9_-]"), "_").take(24)
            val fileName = "${sanitizedName}_${safeQualityId}.$safeExtension"

            val dmRequest = DownloadManager.Request(Uri.parse(targetStreamUrl)).apply {
                quality.requestHeaders.forEach { (name, value) ->
                    if (name.isNotBlank() && value.isNotBlank() && name.length <= 128 && value.length <= 2048) {
                        addRequestHeader(name, value)
                    }
                }
                setTitle(request.title)
""", "download headers and safe filename")

p = root / "app/src/main/java/com/example/data/extractor/MediaExtractorEngine.kt"
s = p.read_text()
old = r'''    fun extractFirstUrlFromSharedText(rawText: String): String? {
        val urlRegex = Regex("""https?://[^\s<>"'\]\)]+""", RegexOption.IGNORE_CASE)
        val match = urlRegex.find(rawText.trim())
        if (match != null) return match.value
        val trimmed = rawText.trim()
        return if (trimmed.contains(".") && !trimmed.contains(" ")) "https://$trimmed" else null
    }

    fun detectPlatformName(url: String): String = when {
        url.contains("youtube.com", true) || url.contains("youtu.be", true) -> "YouTube"
        url.contains("tiktok.com", true) -> "TikTok"
        url.contains("instagram.com", true) -> "Instagram"
        url.contains("facebook.com", true) || url.contains("fb.watch", true) -> "Facebook"
        url.contains("vimeo.com", true) -> "Vimeo"
        url.contains("dailymotion.com", true) || url.contains("dai.ly", true) -> "Dailymotion"
        url.contains("x.com", true) || url.contains("twitter.com", true) -> "X / Twitter"
        url.contains("soundcloud.com", true) -> "SoundCloud"
        url.contains("reddit.com", true) || url.contains("v.redd.it", true) -> "Reddit"
        else -> "الويب"
    }
'''
new = r'''    fun extractFirstUrlFromSharedText(rawText: String): String? {
        val urlRegex = Regex("""(?i)https?://[^\s<>"'\]\)]+""")
        val candidate = urlRegex.find(rawText.trim())?.value
            ?: rawText.trim().takeIf { it.contains('.') && !it.any(Char::isWhitespace) }?.let {
                if (it.startsWith("www.", true)) "https://$it" else "https://$it"
            }
            ?: return null
        val cleaned = candidate.trim().trimEnd('.', ',', ';', ':', '!', '?', ')', ']', '}', '،', '؛', '"', '\\'')
        return runCatching {
            val uri = java.net.URI(cleaned)
            val scheme = uri.scheme?.lowercase(Locale.US)
            val host = uri.host
            if (scheme !in setOf("http", "https") || host.isNullOrBlank() || host == "localhost") null
            else cleaned
        }.getOrNull()
    }

    fun detectPlatformName(url: String): String {
        val host = runCatching { java.net.URI(url).host?.lowercase(Locale.US)?.removePrefix("www.") }.getOrNull().orEmpty()
        fun matches(domain: String) = host == domain || host.endsWith(".$domain")
        return when {
            matches("youtube.com") || matches("youtu.be") || matches("youtube-nocookie.com") -> "YouTube"
            matches("tiktok.com") -> "TikTok"
            matches("instagram.com") -> "Instagram"
            matches("facebook.com") || matches("fb.watch") -> "Facebook"
            matches("vimeo.com") -> "Vimeo"
            matches("dailymotion.com") || matches("dai.ly") -> "Dailymotion"
            matches("x.com") || matches("twitter.com") -> "X / Twitter"
            matches("soundcloud.com") -> "SoundCloud"
            matches("reddit.com") || matches("v.redd.it") -> "Reddit"
            else -> "الويب"
        }
    }
'''
if new not in s:
    if old not in s:
        raise SystemExit("Patch anchor missing: URL extraction/platform detection")
    s = s.replace(old, new, 1)

old_probe = """        runCatching {
            val headReq = Request.Builder()
                .url(url)
                .head()
                .header("User-Agent", MOBILE_USER_AGENT)
                .build()
            httpClient.newCall(headReq).execute().use { resp ->
                if (resp.isSuccessful) {
                    contentType = resp.header("Content-Type").orEmpty().lowercase(Locale.US)
                    contentLength = resp.header("Content-Length")?.toLongOrNull() ?: -1L
                }
            }
        }
"""
new_probe = """        // Some CDNs reject HEAD even though a normal media GET is available.
        runCatching {
            val headReq = Request.Builder()
                .url(url)
                .head()
                .header("User-Agent", MOBILE_USER_AGENT)
                .build()
            httpClient.newCall(headReq).execute().use { resp ->
                if (resp.isSuccessful || resp.code == 206) {
                    contentType = resp.header("Content-Type").orEmpty().lowercase(Locale.US)
                    contentLength = resp.header("Content-Length")?.toLongOrNull()
                        ?: resp.header("Content-Range")?.substringAfterLast('/')?.toLongOrNull()
                        ?: -1L
                }
            }
        }
        if (contentType.isBlank()) {
            runCatching {
                val rangeReq = Request.Builder()
                    .url(url)
                    .get()
                    .header("Range", "bytes=0-0")
                    .header("User-Agent", MOBILE_USER_AGENT)
                    .build()
                httpClient.newCall(rangeReq).execute().use { resp ->
                    contentType = resp.header("Content-Type").orEmpty().lowercase(Locale.US)
                    contentLength = resp.header("Content-Range")?.substringAfterLast('/')?.toLongOrNull()
                        ?: resp.header("Content-Length")?.toLongOrNull()
                        ?: -1L
                }
            }
        }
        // Never mistake a login/error HTML page for a downloadable video just because its URL ends in .mp4.
        if (contentType.startsWith("text/html") || contentType.contains("application/json")) return null
"""
if new_probe not in s:
    if old_probe not in s:
        raise SystemExit("Patch anchor missing: HEAD probe")
    s = s.replace(old_probe, new_probe, 1)

old_quality = """                    mimeType = if (isAudio) "audio/mpeg" else "video/$ext",
                    overrideStreamUrl = streamUrl
                )
"""
new_quality = """                    mimeType = if (isAudio) "audio/mpeg" else "video/$ext",
                    overrideStreamUrl = streamUrl,
                    requestHeaders = mapOf("Referer" to pageUrl, "User-Agent" to MOBILE_USER_AGENT)
                )
"""
if new_quality not in s:
    if old_quality not in s:
        raise SystemExit("Patch anchor missing: scraped quality headers")
    s = s.replace(old_quality, new_quality, 1)

if "private fun resolveMediaUrl(pageUrl: String, rawUrl: String)" not in s:
    anchor = """    private fun extractMetaContent(html: String, propertyName: String): String? {
"""
    helper = """    private fun resolveMediaUrl(pageUrl: String, rawUrl: String): String {
        val cleaned = cleanExtractedUrl(rawUrl)
        return runCatching { java.net.URI(pageUrl).resolve(cleaned).toString() }.getOrDefault(cleaned)
    }

"""
    if anchor not in s:
        raise SystemExit("Patch anchor missing: URL resolver insertion")
    s = s.replace(anchor, helper + anchor, 1)

s = s.replace("""                    if (isPlayableDirectStream(candidate)) {
                        foundStreams.add(cleanExtractedUrl(candidate))
                    }
""", """                    val resolved = resolveMediaUrl(pageUrl, candidate)
                    if (isPlayableDirectStream(resolved)) {
                        foundStreams.add(resolved)
                    }
""", 1)
s = s.replace("""                val url = cleanExtractedUrl(match.groupValues[1])
                if (isPlayableDirectStream(url)) {
                    foundStreams.add(url)
                }
""", """                val url = resolveMediaUrl(pageUrl, match.groupValues[1])
                if (isPlayableDirectStream(url)) {
                    foundStreams.add(url)
                }
""", 1)
p.write_text(s)

test = root / "app/src/test/java/com/example/ExampleUnitTest.kt"
test.write_text('''package com.example

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.example.data.extractor.MediaExtractorEngine
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [36])
class ExampleUnitTest {
    private fun extractor(): MediaExtractorEngine =
        MediaExtractorEngine(ApplicationProvider.getApplicationContext<Context>())

    @Test fun extractsSharedUrlAndStripsArabicSentencePunctuation() {
        assertEquals(
            "https://www.tiktok.com/@mta/video/123456",
            extractor().extractFirstUrlFromSharedText("شاهد: https://www.tiktok.com/@mta/video/123456، الآن")
        )
    }

    @Test fun acceptsBareWwwDomainAndNormalizesScheme() {
        assertEquals("https://www.example.com/video", extractor().extractFirstUrlFromSharedText("www.example.com/video"))
    }

    @Test fun rejectsNonHttpSchemesAndMalformedHostlessUrls() {
        assertNull(extractor().extractFirstUrlFromSharedText("javascript:alert(1)"))
        assertNull(extractor().extractFirstUrlFromSharedText("https:///missing-host"))
    }

    @Test fun platformMatchingUsesHostnameBoundaries() {
        assertEquals("YouTube", extractor().detectPlatformName("https://m.youtube.com/watch?v=abc"))
        assertEquals("الويب", extractor().detectPlatformName("https://notyoutube.com/watch?v=abc"))
    }
}
''')
print("Applied MTA Downloader reliability patches.")
