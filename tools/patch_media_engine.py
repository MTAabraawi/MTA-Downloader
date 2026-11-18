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

replacement = """            MediaExtractionResult.Success(
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
            )"""
source = source[:start] + replacement + source[start + len(anchor):]
target.write_text(source, encoding="utf-8")
print("Patched only the exact Layer 4 fallback call.")
