from pathlib import Path
import sys

target = Path(sys.argv[1])
source = target.read_text(encoding="utf-8")
start = source.find("// Layer 4:")
end = source.find("private fun probeDirectMediaUrl(", start)
if start < 0 or end < 0:
    raise SystemExit(f"Extractor patch anchors missing (start={start}, end={end}); refusing to patch.")
close = source.rfind("        }", start, end)
if close < start:
    raise SystemExit("Could not locate extractMedia method closing brace; refusing to patch.")
line_start = source.rfind("\n", 0, start) + 1
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
            )
"""
target.write_text(source[:line_start] + replacement + source[close:], encoding="utf-8")
print("Patched MediaExtractorEngine: unresolved page URLs now reach local yt-dlp.")
