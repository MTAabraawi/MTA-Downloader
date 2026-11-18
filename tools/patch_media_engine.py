from pathlib import Path
import sys

target = Path(sys.argv[1])
source = target.read_text(encoding="utf-8")
old = '''            // Layer 4: Protected / JS-heavy page -> recommend opening in built-in Smart Browser sniffer
            val reason = if (backendEndpoint.isBlank()) {
                "تستخدم منصة $platform حماية أو مشغل JavaScript ديناميكي. يمكنك فتح الرابط في المتصفح الذكي لالتقاط بث الفيديو أثناء التشغيل، أو إضافة رابط خادم استخراج (yt-dlp / Cobalt) في الإعدادات."
            } else {
                "لم يتم العثور على رابط مباشر عبر خادم الاستخراج. افتح الصفحة في المتصفح الذكي لالتقاط بث الفيديو أثناء تشغيله."
            }
            MediaExtractionResult.NeedsSmartBrowser(
                normalizedUrl = normalizedUrl,
                platform = platform,
                reason = reason
            )
'''
new = '''            // Final layer: pass the page URL to the on-device yt-dlp engine.
            // The rewarded-ad gate remains in MainViewModel before DownloadRepository is called.
            MediaExtractionResult.Success(
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
                    qualities = com.example.data.model.defaultVideoQualities()
                )
            )
'''
if old not in source:
    raise SystemExit("Expected final fallback block was not found; refusing to patch.")
target.write_text(source.replace(old, new, 1), encoding="utf-8")
print("Patched MediaExtractorEngine: page URLs now reach the local extractor.")
