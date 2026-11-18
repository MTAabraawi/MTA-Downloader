from pathlib import Path
import sys

target = Path(sys.argv[1])
source = target.read_text(encoding="utf-8")
start_marker = "            // Layer 4: Protected / JS-heavy page"
end_marker = "\n        }\n\n    private fun probeDirectMediaUrl("
start = source.find(start_marker)
end = source.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("Expected extractor fallback boundary was not found; refusing to patch.")
replacement = """            // Final layer: pass the page URL to the on-device yt-dlp engine.
            // The rewarded-ad gate remains in MainViewModel before DownloadRepository is called.
            MediaExtractionResult.Success(
                VideoItem(
                    id = "page_\u0024{System.currentTimeMillis()}",
                    title = customTitle?.takeIf { it.isNotBlank() } ?: "وسائط من \u0024platform",
                    channelName = platform,
                    channelInitial = platform.firstOrNull()?.uppercase() ?: "M",
                    views = "سيتم تحديد الحجم",
                    publishedAgo = "الآن",
                    duration = "غير محدد",
                    category = "رائج الآن",
                    sourcePlatform = platform,
                    thumbnailRes = R.drawable.img_hero_banner,
                    streamUrl = normalizedUrl,
                    description = "سيحاول محرك yt-dlp المحلي استخراج الوسائط بعد إكمال إعلان المكافأة. قد لا تدعم بعض الروابط أو قد تفرض المنصة قيوداً على الوصول.",
                    qualities = com.example.data.model.defaultVideoQualities()
                )
            )"""
target.write_text(source[:start] + replacement + source[end:], encoding="utf-8")
print("Patched MediaExtractorEngine: page URLs now reach the local extractor.")
