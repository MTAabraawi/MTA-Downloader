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



# MTA Downloader follow-up fixes: browser navigation, server-settings removal, and safer local downloads.
# This pass runs after the initial archive patch above and is intentionally idempotent.

# Fix the malformed Kotlin character literal in the URL cleaner.
p = root / "app/src/main/java/com/example/data/extractor/MediaExtractorEngine.kt"
s = p.read_text()
s = re.sub(
    r'^\s*val cleaned = candidate\.trim\(\)\.trimEnd\(.*$',
    '        val cleaned = candidate.trim().replace(Regex("""[.,;:!?)}\\]،؛"\']+$"""), "")',
    s, count=1, flags=re.M
)

# Remove the optional external extractor endpoint and its API implementation.
for imp in [
    "import android.content.SharedPreferences\n",
    "import kotlinx.serialization.json.Json\n",
    "import kotlinx.serialization.json.JsonArray\n",
    "import kotlinx.serialization.json.JsonObject\n",
    "import kotlinx.serialization.json.JsonPrimitive\n",
    "import kotlinx.serialization.json.contentOrNull\n",
    "import kotlinx.serialization.json.jsonArray\n",
    "import kotlinx.serialization.json.jsonObject\n",
    "import kotlinx.serialization.json.jsonPrimitive\n",
    "import okhttp3.MediaType.Companion.toMediaType\n",
    "import okhttp3.RequestBody.Companion.toRequestBody\n"
]:
    s = s.replace(imp, "")
s = re.sub(r'\n    private val prefs: SharedPreferences = .*?\n', '\n', s, count=1)
s = re.sub(r'\n    private val json = Json \{ ignoreUnknownKeys = true \}\n', '\n', s, count=1)
s = re.sub(r'\n    fun getExtractorEndpoint\(\): String =.*?\n    fun setExtractorEndpoint\(url: String\) \{.*?\n    \}\n', '\n', s, count=1, flags=re.S)
s = re.sub(r'    private fun queryBackendExtractorApi\(.*?(?=    private fun scrapeHtmlForMedia\()', '', s, count=1, flags=re.S)
old = """            // Layer 2: If a custom Cobalt / yt-dlp extraction backend API is configured, query it first
            val backendEndpoint = getExtractorEndpoint()
            if (backendEndpoint.isNotBlank()) {
                queryBackendExtractorApi(backendEndpoint, normalizedUrl, platform, customTitle)?.let { apiItem ->
                    return@withContext MediaExtractionResult.Success(apiItem)
                }
            }

            // Layer 3: On-device HTML / OpenGraph / JSON-LD / <video> stream scraping
            scrapeHtmlForMedia(normalizedUrl, platform, customTitle)?.let { scrapedItem ->
                return@withContext MediaExtractionResult.Success(scrapedItem)
            }

            // Layer 4: Protected / JS-heavy page -> recommend opening in built-in Smart Browser sniffer
            val reason = if (backendEndpoint.isBlank()) {
                "تستخدم منصة $platform حماية أو مشغل JavaScript ديناميكي. يمكنك فتح الرابط في المتصفح الذكي لالتقاط بث الفيديو أثناء التشغيل، أو إضافة رابط خادم استخراج (yt-dlp / Cobalt) في الإعدادات."
            } else {
                "لم يتم العثور على رابط مباشر عبر خادم الاستخراج. افتح الصفحة في المتصفح الذكي لالتقاط بث الفيديو أثناء تشغيله."
            }
"""
new = """            // Local metadata extraction only. No user-configured third-party extraction server.
            scrapeHtmlForMedia(normalizedUrl, platform, customTitle)?.let { scrapedItem ->
                return@withContext MediaExtractionResult.Success(scrapedItem)
            }

            val reason = "لم يعثر المحرك المحلي على رابط وسائط مباشر قابل للتنزيل من $platform. افتح الصفحة في المتصفح الداخلي وشغّل المحتوى العام؛ سيظهر زر التحميل عند التقاط رابط مباشر مدعوم. قد تمنع المنصة تنزيل بعض المقاطع أو تتطلب استخدام ميزات التنزيل الرسمية."
"""
s = s.replace(old, new)
s = s.replace(' * 2. Configurable Extractor Backend API (Cobalt / yt-dlp compatible JSON endpoint)\n',
              ' * 2. On-device public HTML and metadata extraction\n')
s = s.replace('''        private const val PREFS_NAME = "mta_extractor_prefs"
        private const val KEY_EXTRACTOR_ENDPOINT = "extractor_endpoint_url"
''', "")
s = s.replace('''                .url(url)
                .url(url)
''', '''                .url(url)
''')
s = s.replace('resp.header("Content-Type").orEmpty().lowercase(Locale.US)',
              'resp.header("Content-Type").orEmpty().substringBefore(\';\').trim().lowercase(Locale.US)')
s = s.replace('''        val isVideo = contentType.startsWith("video/") || lower.endsWith(".mp4") ||
            lower.endsWith(".webm") || lower.endsWith(".mov") || lower.endsWith(".m4v")
''', '''        val isVideo = contentType in setOf("video/mp4", "video/webm", "video/quicktime", "video/x-m4v") ||
            lower.endsWith(".mp4") || lower.endsWith(".webm") || lower.endsWith(".mov") || lower.endsWith(".m4v")
''')
s = s.replace('''            lower.endsWith(".mp3") || contentType.contains("mpeg") -> "mp3"
            lower.endsWith(".m4a") || contentType.contains("mp4a") -> "m4a"
            lower.endsWith(".webm") || contentType.contains("webm") -> "webm"
            else -> "mp4"
        }
        val mime = if (isAudio) "audio/mpeg" else "video/$ext"
''', '''            lower.endsWith(".mp3") || contentType.contains("mpeg") -> "mp3"
            lower.endsWith(".m4a") || contentType.contains("mp4a") || contentType == "audio/mp4" -> "m4a"
            lower.endsWith(".webm") || contentType.contains("webm") -> "webm"
            lower.endsWith(".mov") || contentType.contains("quicktime") -> "mov"
            lower.endsWith(".m4v") -> "m4v"
            else -> "mp4"
        }
        val mime = when {
            isAudio && ext == "m4a" -> "audio/mp4"
            isAudio -> "audio/mpeg"
            ext == "mov" -> "video/quicktime"
            else -> "video/$ext"
        }
''')
s = s.replace('(?:mp4|m4v|webm|mp3|m4a)', '(?:mp4|m4v|webm|mov|mp3|m4a)')
s = s.replace('''            val tagSrcRegex = Regex(
                """<(?:video|source)[^>]+src=["'](https?://[^"']+)["']""",
                RegexOption.IGNORE_CASE
            )
''', '''            val tagSrcRegex = Regex(
                """<(?:video|source)[^>]+src=["']([^"']+)["']""",
                RegexOption.IGNORE_CASE
            )
''')
if "private fun resolveMediaUrl(pageUrl: String, rawUrl: String)" not in s:
    anchor = "    private fun extractMetaContent(html: String, propertyName: String): String? {"
    helper = """    private fun resolveMediaUrl(pageUrl: String, rawUrl: String): String {
        val cleaned = cleanExtractedUrl(rawUrl)
        return runCatching { java.net.URI(pageUrl).resolve(cleaned).toString() }.getOrDefault(cleaned)
    }

"""
    s = s.replace(anchor, helper + anchor, 1)
s = s.replace('''                    if (isPlayableDirectStream(candidate)) {
                        foundStreams.add(cleanExtractedUrl(candidate))
                    }
''', '''                    val resolved = resolveMediaUrl(pageUrl, candidate)
                    if (isPlayableDirectStream(resolved)) foundStreams.add(resolved)
''')
s = s.replace('''                val url = cleanExtractedUrl(match.groupValues[1])
                if (isPlayableDirectStream(url)) {
                    foundStreams.add(url)
                }
''', '''                val url = resolveMediaUrl(pageUrl, match.groupValues[1])
                if (isPlayableDirectStream(url)) foundStreams.add(url)
''')
s = s.replace('''                val cleaned = cleanExtractedUrl(match.value)
                if (!cleaned.contains("preview_empty", true)) {
                    foundStreams.add(cleaned)
                }
''', '''                val cleaned = resolveMediaUrl(pageUrl, match.value)
                if (isPlayableDirectStream(cleaned) && !cleaned.contains("preview_empty", true)) {
                    foundStreams.add(cleaned)
                }
''')
s = s.replace('''                    lower.endsWith(".webm") -> "webm"
                    else -> "mp4"
                }
''', '''                    lower.endsWith(".webm") -> "webm"
                    lower.endsWith(".mov") -> "mov"
                    else -> "mp4"
                }
''')
s = s.replace('''                    mimeType = if (isAudio) "audio/mpeg" else "video/$ext",
''', '''                    mimeType = when {
                        isAudio && ext == "m4a" -> "audio/mp4"
                        isAudio -> "audio/mpeg"
                        ext == "mov" -> "video/quicktime"
                        else -> "video/$ext"
                    },
''')
s = s.replace('''            lower.endsWith(".webm") || lower.endsWith(".mp3") ||
                lower.endsWith(".m4a")
''', '''            lower.endsWith(".webm") || lower.endsWith(".mov") || lower.endsWith(".mp3") ||
                lower.endsWith(".m4a")
''')
p.write_text(s)

# Remove experimental extractor-server UI and state.
p = root / "app/src/main/java/com/example/ui/MainViewModel.kt"
s = p.read_text()
s = re.sub(r'\n    private val _showSettingsDialog = MutableStateFlow\(false\)\n    val showSettingsDialog: StateFlow<Boolean> = _showSettingsDialog\n\n    private val _extractorEndpoint = MutableStateFlow\(mediaExtractorEngine\.getExtractorEndpoint\(\)\)\n    val extractorEndpoint: StateFlow<String> = _extractorEndpoint\n', '\n', s, count=1)
s = re.sub(r'\n    fun openSettingsDialog\(\) \{.*?\n    \}\n\n    fun requestVideoDownload', '\n    fun requestVideoDownload', s, count=1, flags=re.S)
s = s.replace('''data class BrowserState(
    val activeUrl: String = "",
    val addressInput: String = "",
''', '''data class BrowserState(
    val activeUrl: String = "",
    val currentPageUrl: String = "",
    val addressInput: String = "",
''')
s = s.replace('''            val platform = mediaExtractorEngine.detectPlatformName(state.activeUrl)
            val videoItem = catalogRepository.buildFromCapturedBrowserStreams(
                streams = captured,
                pageTitle = state.pageTitle,
                platform = platform
            )
            requestVideoDownload(videoItem)
        } else if (state.activeUrl.isNotBlank()) {
            analyzeAndRequestUrlDownload(state.activeUrl)
''', '''            val pageUrl = state.currentPageUrl.ifBlank { state.activeUrl }
            val platform = mediaExtractorEngine.detectPlatformName(pageUrl)
            val videoItem = catalogRepository.buildFromCapturedBrowserStreams(
                streams = captured,
                pageTitle = state.pageTitle,
                platform = platform
            )
            val withHeaders = videoItem.copy(qualities = videoItem.qualities.map { quality ->
                quality.copy(requestHeaders = quality.requestHeaders + mapOf(
                    "Referer" to pageUrl,
                    "User-Agent" to "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"
                ))
            })
            requestVideoDownload(withHeaders)
        } else if (state.currentPageUrl.isNotBlank() || state.activeUrl.isNotBlank()) {
            analyzeAndRequestUrlDownload(state.currentPageUrl.ifBlank { state.activeUrl })
''')
s = s.replace('''                activeUrl = normalized,
                addressInput = normalized,
''', '''                activeUrl = normalized,
                currentPageUrl = normalized,
                addressInput = normalized,
''')
s = s.replace('''            val urlChanged = !url.isNullOrBlank() && url != state.activeUrl && isLoading && progress <= 20
            state.copy(
                addressInput = url ?: state.addressInput,
''', '''            val pageChanged = !url.isNullOrBlank() && url != state.currentPageUrl && isLoading && progress <= 25
            state.copy(
                currentPageUrl = url ?: state.currentPageUrl,
                addressInput = url ?: state.addressInput,
''')
s = s.replace('detectedStreams = if (urlChanged) emptyList() else state.detectedStreams',
              'detectedStreams = if (pageChanged) emptyList() else state.detectedStreams')
s = s.replace('if (!mediaUrl.startsWith("http")) return',
              'if (!mediaUrl.startsWith("https://", true) && !mediaUrl.startsWith("http://", true)) return')
s = s.replace('if (lower.endsWith(".ts") || lower.endsWith(".m4s")) return',
              'if (lower.endsWith(".ts") || lower.endsWith(".m4s") || lower.endsWith(".m3u8") || lower.endsWith(".mpd")) return')
s = s.replace('''            lower.endsWith(".mp3") -> "mp3"
            lower.endsWith(".m4a") -> "m4a"
            lower.endsWith(".webm") -> "webm"
            else -> "mp4"
''', '''            lower.endsWith(".mp3") || mimeHint?.contains("audio/mpeg", true) == true -> "mp3"
            lower.endsWith(".m4a") || mimeHint?.contains("audio/mp4", true) == true -> "m4a"
            lower.endsWith(".webm") || mimeHint?.contains("video/webm", true) == true -> "webm"
            lower.endsWith(".mov") || mimeHint?.contains("quicktime", true) == true -> "mov"
            else -> "mp4"
''')
s = s.replace('''        val mime = if (isAudio) "audio/mpeg" else "video/$ext"
''', '''        val mime = when {
            isAudio && ext == "m4a" -> "audio/mp4"
            isAudio -> "audio/mpeg"
            ext == "mov" -> "video/quicktime"
            else -> "video/$ext"
        }
''')
p.write_text(s)

# Remove the home-screen server-settings shortcut.
p = root / "app/src/main/java/com/example/ui/screens/HomeScreen.kt"
s = p.read_text().replace("import androidx.compose.material.icons.filled.Settings\n", "")
s = s.replace('''    onOpenDownloadsClick: () -> Unit,
    onOpenSettingsClick: () -> Unit,
''', '''    onOpenDownloadsClick: () -> Unit,
''')
s = s.replace('''                    activeDownloadsCount = activeDownloadsCount,
                    onDownloadsBadgeClick = onOpenDownloadsClick,
                    onSettingsClick = onOpenSettingsClick
''', '''                    activeDownloadsCount = activeDownloadsCount,
                    onDownloadsBadgeClick = onOpenDownloadsClick
''')
s = s.replace("المواقع المدعومة للتحميل السريع", "مواقع يمكن تصفحها والتقاط روابط الوسائط العامة منها")
s = s.replace('''    onDownloadsBadgeClick: () -> Unit,
    onSettingsClick: () -> Unit
''', '''    onDownloadsBadgeClick: () -> Unit
''')
s = re.sub(r'\n            IconButton\(\n                onClick = onSettingsClick,.*?\n            \}\n\n', '\n', s, count=1, flags=re.S)
p.write_text(s)

# Remove server settings action/dialog from the fallback and dialogs.
p = root / "app/src/main/java/com/example/ui/components/MtaDialogs.kt"
s = p.read_text()
s = s.replace("import androidx.compose.material.icons.filled.Settings\n", "")
s = s.replace("import androidx.compose.material.icons.filled.Share\n", "")
s = s.replace('''    prompt: SmartBrowserFallbackPrompt,
    onOpenInSmartBrowser: (String) -> Unit,
    onOpenExtractorSettings: () -> Unit,
    onDismiss: () -> Unit
''', '''    prompt: SmartBrowserFallbackPrompt,
    onOpenInSmartBrowser: (String) -> Unit,
    onDismiss: () -> Unit
''')
s = re.sub(r'\n                TextButton\(\n                    onClick = \{\n                        onDismiss\(\)\n                        onOpenExtractorSettings\(\).*?\n                \}\n', '\n', s, count=1, flags=re.S)
s = re.sub(r'\n@Composable\nfun ExtractorSettingsDialog\(.*?(?=\n@Composable\nfun AdLoadingOverlayDialog\()', '', s, count=1, flags=re.S)
p.write_text(s)

# MainActivity: fix restored browser-route overriding the newly selected site.
p = root / "app/src/main/java/com/example/MainActivity.kt"
s = p.read_text()
s = s.replace("import com.example.ui.components.ExtractorSettingsDialog\n", "")
s = s.replace("import androidx.navigation.toRoute\n", "")
s = s.replace('''    val showSettingsDialog by viewModel.showSettingsDialog.collectAsStateWithLifecycle()
    val extractorEndpoint by viewModel.extractorEndpoint.collectAsStateWithLifecycle()
''', "")
s = s.replace('''                                onOpenDownloadsClick = { navigateTopLevel(DownloadsRoute) },
                                onOpenSettingsClick = viewModel::openSettingsDialog
''', '''                                onOpenDownloadsClick = { navigateTopLevel(DownloadsRoute) }
''')
s = re.sub(r'composable<BrowserRoute> \{ entry ->\s*val route = entry\.toRoute<BrowserRoute>\(\)\s*LaunchedEffect\(route\.initialUrl\) \{.*?\n                            BrowserScreen\(', 'composable<BrowserRoute> {\n                            BrowserScreen(', s, count=1, flags=re.S)
s = s.replace('''            onOpenExtractorSettings = viewModel::openSettingsDialog,
''', "")
s = re.sub(r'\n    // Extractor Engine Settings Dialog\n    if \(showSettingsDialog\) \{.*?\n    \}\n', '\n', s, count=1, flags=re.S)
s = re.sub(r'    private fun handleIncomingShareIntent\(intent: Intent\?\) \{.*?\n    \}', '''    private fun handleIncomingShareIntent(intent: Intent?) {
        if (!::mainViewModel.isInitialized || intent == null) return
        val sharedText = when (intent.action) {
            Intent.ACTION_SEND -> intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString()
            Intent.ACTION_SEND_MULTIPLE -> intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString()
                ?: intent.getParcelableArrayListExtra<android.net.Uri>(Intent.EXTRA_STREAM)?.firstOrNull()?.toString()
            Intent.ACTION_VIEW -> intent.dataString
            else -> null
        }
        if (!sharedText.isNullOrBlank()) mainViewModel.handleSharedTextFromExternalApp(sharedText)
    }''', s, count=1, flags=re.S)
p.write_text(s)

# Browser: WebView cleanup, safer WebSettings, current-page capture and no timer polling.
p = root / "app/src/main/java/com/example/ui/screens/BrowserScreen.kt"
s = p.read_text()
s = s.replace("import android.webkit.WebSettings\n", "import android.webkit.WebSettings\nimport android.webkit.SslErrorHandler\nimport android.os.Build\n")
s = s.replace("import androidx.compose.runtime.Composable\n", "import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.DisposableEffect\nimport androidx.compose.runtime.onDispose\n")
s = s.replace('''    var webViewRef by remember { mutableStateOf<WebView?>(null) }

    Box(
''', '''    var webViewRef by remember { mutableStateOf<WebView?>(null) }

    DisposableEffect(browserState.activeUrl.isNotBlank()) {
        onDispose {
            webViewRef?.apply {
                stopLoading()
                removeJavascriptInterface("MTABridge")
                destroy()
            }
            webViewRef = null
        }
    }

    Box(
''')
s = s.replace("settings.mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE",
              "settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW")
s = s.replace('''                            settings.loadWithOverviewMode = true

                            addJavascriptInterface(
''', '''                            settings.loadWithOverviewMode = true
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            settings.javaScriptCanOpenWindowsAutomatically = false
                            settings.setSupportMultipleWindows(false)
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) settings.safeBrowsingEnabled = true

                            addJavascriptInterface(
''')
s = s.replace("setInterval(scanMedia, 2500);", """document.addEventListener('loadedmetadata', scanMedia, true);
                                                document.addEventListener('play', scanMedia, true);
                                                document.addEventListener('canplay', scanMedia, true);""")
s = s.replace('if (src.startsWith("http")) {',
              'if (src.startsWith("https://", true) || src.startsWith("http://", true)) {')
s = s.replace('if (url.startsWith("http")) {',
              'if (url.startsWith("https://", true) || url.startsWith("http://", true)) {')
s = s.replace('''                            webViewClient = object : WebViewClient() {
                                override fun onPageStarted(
''', '''                            webViewClient = object : WebViewClient() {
                                override fun onReceivedSslError(
                                    view: WebView?,
                                    handler: SslErrorHandler?,
                                    error: android.net.http.SslError?
                                ) {
                                    handler?.cancel()
                                }

                                override fun onPageStarted(
''')
s = s.replace('''                                        lower.endsWith(".webm") ||
                                        lower.endsWith(".mp3") ||
''', '''                                        lower.endsWith(".webm") ||
                                        lower.endsWith(".mov") ||
                                        lower.endsWith(".mp3") ||
''')
p.write_text(s)

# Accurate supported-site labels (not guarantees of universal download availability).
p = root / "app/src/main/java/com/example/data/repository/VideoCatalogRepository.kt"
s = p.read_text()
for a, b in {
    'tag = "فيديو 4K"': 'tag = "تصفح الوسائط"',
    'tag = "بدون علامة"': 'tag = "روابط عامة"',
    'tag = "Reels"': 'tag = "مقاطع عامة"',
    'tag = "HD"': 'tag = "روابط عامة"',
    'tag = "MP4"': 'tag = "فيديو عام"',
    'tag = "Full HD"': 'tag = "فيديو عام"',
    'tag = "سريع"': 'tag = "وسائط عامة"',
    'tag = "MP3"': 'tag = "صوت عام"',
}.items():
    s = s.replace(a, b)
p.write_text(s)

# TLS-only network policy and remove obsolete setting string.
p = root / "app/src/main/AndroidManifest.xml"
s = p.read_text().replace('android:usesCleartextTraffic="true"', 'android:usesCleartextTraffic="false"')
p.write_text(s)
p = root / "app/src/main/res/values/strings.xml"
s = '\n'.join(line for line in p.read_text().splitlines() if "extractor_settings_title" not in line) + '\n'
p.write_text(s)

# Reject malformed stream URLs before handing them to DownloadManager.
p = root / "app/src/main/java/com/example/data/repository/DownloadRepository.kt"
s = p.read_text()
s = s.replace('''            val targetStreamUrl = quality.overrideStreamUrl?.takeIf { it.isNotBlank() } ?: request.streamUrl
''', '''            val targetStreamUrl = quality.overrideStreamUrl?.takeIf { it.isNotBlank() } ?: request.streamUrl
            require(targetStreamUrl.startsWith("https://", true) || targetStreamUrl.startsWith("http://", true)) {
                "رابط التنزيل غير صالح"
            }
''')
p.write_text(s)

