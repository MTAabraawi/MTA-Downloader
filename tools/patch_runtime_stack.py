#!/usr/bin/env python3
"""Apply the reviewed Retrofit/Jsoup/Media3 integration to the extracted Android project."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "project")

def patch(path: str, old: str, new: str, label: str) -> None:
    file = root / path
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Patch anchor missing ({label}) in {path}; refusing a partial patch")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")

# Pass the real Room download records to the redesigned home screen.
patch(
    "app/src/main/java/com/example/MainActivity.kt",
    "                                supportedSites = viewModel.supportedSites,\n                                activeDownloadsCount = activeDownloadsCount,",
    "                                supportedSites = viewModel.supportedSites,\n                                activeDownloadsCount = activeDownloadsCount,\n                                recentDownloads = downloads.take(4),",
    "recent download records",
)

# Replace the legacy platform VideoView with lifecycle-aware Media3 ExoPlayer.
dialogs = root / "app/src/main/java/com/example/ui/components/MtaDialogs.kt"
text = dialogs.read_text(encoding="utf-8")
for import_line in (
    "import android.net.Uri\n",
    "import android.widget.MediaController\n",
    "import android.widget.VideoView\n",
    "import androidx.compose.ui.viewinterop.AndroidView\n",
):
    text = text.replace(import_line, "")
old_player = re.compile(
    r"AndroidView\(\s*factory = \{ ctx ->\s*"
    r"VideoView\(ctx\)\.apply \{.*?\n\s*\},\s*"
    r"modifier = Modifier\.fillMaxWidth\(\)\s*\)\s*",
    re.S,
)
new_player = """                    Media3VideoPlayer(
                        mediaUrl = media.mediaUrl,
                        modifier = Modifier.fillMaxWidth()
                    )
"""
if "Media3VideoPlayer(" not in text:
    text, count = old_player.subn(new_player, text, count=1)
    if count != 1:
        raise SystemExit("Could not safely locate the legacy VideoView player block")
dialogs.write_text(text, encoding="utf-8")

# Retrofit uses the existing hardened OkHttp client; Jsoup parses real HTML structure.
engine = root / "app/src/main/java/com/example/data/extractor/MediaExtractorEngine.kt"
text = engine.read_text(encoding="utf-8")
if "import retrofit2.Retrofit" not in text:
    text = text.replace("import okhttp3.Request\n", "import okhttp3.Request\nimport retrofit2.Retrofit\n")
if "private val pageApi: PublicPageApi = Retrofit.Builder()" not in text:
    anchor = """        .build()



    fun extractFirstUrlFromSharedText"""
    replacement = """        .build()

    private val pageApi: PublicPageApi = Retrofit.Builder()
        .baseUrl("https://example.invalid/")
        .client(httpClient)
        .build()
        .create(PublicPageApi::class.java)

    fun extractFirstUrlFromSharedText"""
    if anchor not in text:
        raise SystemExit("Could not find MediaExtractorEngine client initialization")
    text = text.replace(anchor, replacement, 1)

text = text.replace("    private fun scrapeHtmlForMedia(\n", "    private suspend fun scrapeHtmlForMedia(\n", 1)
old_fetch = re.compile(
    r"            val request = Request\.Builder\(\).*?"
    r"            if \(html\.isBlank\(\)\) return@runCatching null",
    re.S,
)
new_fetch = """            val response = pageApi.fetchPage(
                pageUrl,
                mapOf(
                    "User-Agent" to MOBILE_USER_AGENT,
                    "Accept" to "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                )
            )
            if (!response.isSuccessful) return@runCatching null
            val contentType = response.headers()["Content-Type"].orEmpty()
            if (!contentType.contains("text/html", true) && !contentType.contains("json", true)) {
                return@runCatching null
            }
            val html = response.body()?.string()?.take(600_000).orEmpty()
            if (html.isBlank()) return@runCatching null

            val document = HtmlMediaDocumentParser.parse(html, pageUrl)"""
if "val response = pageApi.fetchPage(" not in text:
    text, count = old_fetch.subn(new_fetch, text, count=1)
    if count != 1:
        raise SystemExit("Could not safely replace the page-fetch block with Retrofit")

old_metadata = """            val title = customTitle?.takeIf { it.isNotBlank() }
                ?: extractMetaContent(html, "og:title")
                ?: extractHtmlTitle(html)
                ?: "فيديو من $platform"

            val thumbnail = extractMetaContent(html, "og:image")
                ?: extractMetaContent(html, "twitter:image")"""
new_metadata = """            val title = customTitle?.takeIf { it.isNotBlank() }
                ?: document.title
                ?: "فيديو من $platform"

            val thumbnail = document.thumbnailUrl"""
if new_metadata not in text:
    if old_metadata not in text:
        raise SystemExit("Could not locate HTML metadata extraction block")
    text = text.replace(old_metadata, new_metadata, 1)

old_html5 = """            // 2. HTML5 <video src="..."> and <source src="...">
            val tagSrcRegex = Regex(
                \"\"\"<(?:video|source)[^>]+src=["']([^"']+)["']\"\"\",
                RegexOption.IGNORE_CASE
            )
            tagSrcRegex.findAll(html).forEach { match ->
                val url = resolveMediaUrl(pageUrl, match.groupValues[1])
                if (isPlayableDirectStream(url)) {
                    foundStreams.add(url)
                }
            }"""
new_html5 = """            // 2. HTML5 video/source nodes parsed with the HTML5 DOM parser.
            document.streamUrls.forEach { candidate ->
                val url = resolveMediaUrl(pageUrl, candidate)
                if (isPlayableDirectStream(url)) foundStreams.add(url)
            }"""
if new_html5 not in text:
    if old_html5 not in text:
        raise SystemExit("Could not locate HTML5 video/source regex block")
    text = text.replace(old_html5, new_html5, 1)

engine.write_text(text, encoding="utf-8")
print("Runtime stack patch applied: Retrofit page fetching, Jsoup metadata parsing, Media3 player, recent downloads.")
