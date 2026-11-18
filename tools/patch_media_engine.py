from pathlib import Path
import sys

target = Path(sys.argv[1])
source = target.read_text(encoding="utf-8")

anchor = """            MediaExtractionResult.NeedsSmartBrowser(
                normalizedUrl = normalizedUrl,
                platform = platform,
                reason = reason
            )"""
start = source.find(anchor)
if start < 0:
    raise SystemExit("Exact Layer 4 NeedsSmartBrowser fallback block not found; refusing to patch.")

# Replace the complete Layer 4 reason + result expression, preserving the function body.
reason_start = source.rfind("            val reason =", 0, start)
if reason_start < 0:
    raise SystemExit("Layer 4 reason declaration not found; refusing to patch.")
line_start = source.rfind(chr(10), 0, reason_start) + 1
line_end = source.find(chr(10), start + len(anchor))
if line_end < 0:
    raise SystemExit("Could not find end of Layer 4 fallback; refusing to patch.")
line_end += 1

replacement = """            // Layer 4: pass unresolved page URLs to the on-device yt-dlp engine.
            // The rewarded-ad gate remains in MainViewModel before the repository starts.
            return@withContext MediaExtractionResult.Success(
                VideoItem(
                    id = "page_${System.currentTimeMillis()}",
                    title = customTitle?.takeIf { it.isNotBlank() } ?: "وسائط من $platform",
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
                    qualities = listOf(
                        QualityOption(
                            id = "best",
                            label = "أفضل جودة متاحة",
                            format = "MP4",
                            sizeEstimate = "تلقائي",
                            extension = "mp4",
                            mimeType = "video/mp4",
                            overrideStreamUrl = normalizedUrl
                        )
                    )
                )
            )
"""
target.write_text(source[:line_start] + replacement + source[line_end:], encoding="utf-8")
print("Patched Layer 4 fallback safely.")
