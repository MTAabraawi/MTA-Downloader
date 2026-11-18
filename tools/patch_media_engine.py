from pathlib import Path
import sys

target = Path(sys.argv[1])
source = target.read_text(encoding="utf-8")

# Locate the fallback by its Kotlin expression, not by comments or whitespace.
call = source.find("MediaExtractionResult.NeedsSmartBrowser(")
if call < 0:
    raise SystemExit("NeedsSmartBrowser fallback call not found; refusing to patch.")

reason = source.rfind("val reason =", 0, call)
if reason < 0:
    raise SystemExit("Fallback reason declaration not found; refusing to patch.")

# Find the closing parenthesis of NeedsSmartBrowser(...) with balanced delimiters.
open_paren = source.find("(", call)
depth = 0
close_paren = -1
for i in range(open_paren, len(source)):
    ch = source[i]
    if ch == "(":
        depth += 1
    elif ch == ")":
        depth -= 1
        if depth == 0:
            close_paren = i + 1
            break
if close_paren < 0:
    raise SystemExit("Could not balance NeedsSmartBrowser call; refusing to patch.")

# Include the reason declaration and the complete fallback expression.
line_start = source.rfind("\\n", 0, reason) + 1
line_end = source.find("\\n", close_paren)
if line_end < 0:
    line_end = len(source)
else:
    line_end += 1

replacement = """            // Final layer: route unresolved page URLs to the on-device yt-dlp engine.
            // The existing rewarded-ad gate is retained in the download flow.
            return@withContext MediaExtractionResult.Success(
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
            )
"""
target.write_text(source[:line_start] + replacement + source[line_end:], encoding="utf-8")
print("Patched fallback by Kotlin call expression.")
