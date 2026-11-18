from pathlib import Path
import re
import sys

argument = Path(sys.argv[1])
if argument.is_file():
    target = argument
    root = target.parents[8]
else:
    root = argument
    target = root / "app/src/main/java/com/example/data/extractor/MediaExtractorEngine.kt"
source = target.read_text(encoding="utf-8")

# Add native NewPipe extraction after direct-file probing and before generic HTML parsing.
native_anchor = re.compile(
    r"(probeDirectMediaUrl\(normalizedUrl, platform, customTitle\)\?\.let \{ directItem ->"
    r"\s*return@withContext MediaExtractionResult\.Success\(directItem\)\s*\})"
)
if "NewPipeMediaProvider.extract(" not in source:
    source, count = native_anchor.subn(
        r"""\1

            // Native provider first for supported services; yt-dlp remains the broad fallback.
            MediaExtractionRouter.extract(normalizedUrl, customTitle, platform)?.let { extractedItem ->
                return@withContext MediaExtractionResult.Success(extractedItem)
            }""",
        source,
        count=1
    )
    if count != 1:
        raise SystemExit("Could not wire NewPipe provider into MediaExtractorEngine.")

manifest_anchor = """        // Never mistake a login/error HTML page for a downloadable video just because its URL ends in .mp4.
        if (contentType.startsWith("text/html") || contentType.contains("application/json")) return null"""
manifest_replacement = """        // HLS/DASH are manifests, not standalone MP4 files; route them to an extractor/remux-capable path.
        val browserReference = MediaExtractionRouter.classifyBrowserMedia(url, contentType)
        if (browserReference?.kind == BrowserMediaKind.HLS_MANIFEST ||
            browserReference?.kind == BrowserMediaKind.DASH_MANIFEST) return null

""" + manifest_anchor
if "BrowserMediaParser.parse(url, contentType)" not in source:
    if manifest_anchor not in source:
        raise SystemExit("Could not wire BrowserMediaParser into direct-media probing.")
    source = source.replace(manifest_anchor, manifest_replacement, 1)

target.write_text(source, encoding="utf-8")

# NewPipe Extractor is published through JitPack. Add it only to dependency-resolution repositories.
def configure_jitpack():
    candidates = [root / "settings.gradle.kts", root / "settings.gradle"]
    settings = next((p for p in candidates if p.exists()), None)
    if settings is None:
        raise SystemExit("Gradle settings file not found; cannot configure NewPipe repository safely.")
    content = settings.read_text(encoding="utf-8")
    if "https://jitpack.io" in content:
        return
    scope = content.find("dependencyResolutionManagement")
    if scope >= 0:
        match = re.search(r"repositories\s*\{", content[scope:])
        if not match:
            raise SystemExit("dependencyResolutionManagement repositories block not found.")
        position = scope + match.end()
        content = content[:position] + '\n        maven { url = uri("https://jitpack.io") }' + content[position:]
    else:
        content += '\n\ndependencyResolutionManagement {\n    repositories {\n        maven { url = uri("https://jitpack.io") }\n    }\n}\n'
    settings.write_text(content, encoding="utf-8")

configure_jitpack()

# Avoid unstable Gradle configuration-cache serialization in the archived Android project.
gradle_properties = root / "gradle.properties"
if gradle_properties.exists():
    gradle_text = gradle_properties.read_text(encoding="utf-8")
    if "org.gradle.configuration-cache=" not in gradle_text:
        gradle_properties.write_text(
            gradle_text.rstrip() + "\\norg.gradle.configuration-cache=false\\n",
            encoding="utf-8"
        )

anchor = """            MediaExtractionResult.NeedsSmartBrowser(
                normalizedUrl = normalizedUrl,
                platform = platform,
                reason = reason
            )"""
start = source.find(anchor)
if start < 0:
    raise SystemExit("Exact Layer 4 NeedsSmartBrowser fallback block not found; refusing to patch.")
reason_start = source.rfind("            val reason =", 0, start)
if reason_start < 0:
    raise SystemExit("Layer 4 reason declaration not found; refusing to patch.")
line_start = source.rfind("\n", 0, reason_start) + 1
line_end = source.find("\n", start + len(anchor))
if line_end < 0:
    raise SystemExit("Could not find end of Layer 4 fallback; refusing to patch.")
line_end += 1
replacement = """            // Layer 4: unresolved public page URLs are handed to the on-device yt-dlp engine.
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
                    description = "سيحلل محرك yt-dlp المحلي الصفحة ويحاول استخراج الصيغ المتاحة. قد لا تدعم بعض الروابط أو قد تفرض المنصة قيوداً على الوصول.",
                    qualities = listOf(
                        QualityOption(
                            id = "best",
                            label = "أفضل جودة متاحة",
                            format = "تلقائي",
                            sizeEstimate = "يحددها المحرك",
                            extension = "mp4",
                            mimeType = "video/mp4",
                            overrideStreamUrl = normalizedUrl
                        )
                    )
                )
            )
"""
target.write_text(source[:line_start] + replacement + source[line_end:], encoding="utf-8")

def edit(rel, transform):
    p = root / rel
    if not p.exists():
        raise SystemExit(f"Required source file missing: {rel}")
    old = p.read_text(encoding="utf-8")
    new = transform(old)
    if new != old:
        p.write_text(new, encoding="utf-8")

def replace_required(s, old, new, label):
    if old not in s:
        raise SystemExit(f"Expected source block not found: {label}")
    return s.replace(old, new, 1)

# Remove every ad SDK reference and Android advertising identifier.
def gradle(s):
    s = re.sub(r"^.*Start\.io rewarded ads.*\n", "", s, flags=re.M)
    s = re.sub(r"^.*com\.startapp:inapp-sdk.*\n", "", s, flags=re.M)
    return s
edit("app/build.gradle.kts", gradle)

def manifest(s):
    s = s.replace('    <uses-permission android:name="com.google.android.gms.permission.AD_ID" />\n', "")
    s = re.sub(r"\s*<meta-data\s+android:name=\"com\.startapp\.sdk\.APPLICATION_ID\"\s+android:value=\"210745939\"\s*/>\s*", "\n", s)
    return s
edit("app/src/main/AndroidManifest.xml", manifest)

def app(s):
    s = s.replace("import com.startapp.sdk.adsbase.StartAppAd\n", "")
    s = s.replace("import com.startapp.sdk.adsbase.StartAppSDK\n", "")
    block = """        // Preserve the existing Start.io app ID and initialization.
        StartAppSDK.initParams(this, STARTIO_APP_ID)
            .setReturnAdsEnabled(false)
            .init()
        StartAppAd.disableSplash()
"""
    if block in s:
        s = s.replace(block, "", 1)
    elif "StartAppSDK" in s or "StartAppAd" in s:
        raise SystemExit("Unrecognized Start.io initialization remains; refusing unsafe partial removal.")
    # The clean overlay already removes Start.io initialization, so absence is expected.
    s = re.sub(r"\n    companion object \{\n        const val STARTIO_APP_ID = \"210745939\"\n    \}\n", "\n", s)
    return s
edit("app/src/main/java/com/example/MTADownloaderApp.kt", app)

# MainViewModel: replace reward gating with a direct user-confirmed download action.
def viewmodel(s):
    s = s.replace("import android.app.Activity\n", "")
    s = s.replace("import com.example.ads.StartIoRewardedAdManager\n", "")
    s = s.replace("RewardDialogState", "DownloadOptionsState")
    s = s.replace("_rewardDialogState", "_downloadOptionsState").replace("rewardDialogState", "downloadOptionsState")
    s = s.replace("dismissRewardConfirmationDialog", "dismissDownloadOptionsDialog")
    s = s.replace("""    val isLoadingAd: Boolean = false,
    val adErrorMessage: String? = null,
    val lastAttemptedRequest: PendingDownloadRequest? = null,
    val lastAttemptedQuality: QualityOption? = null
""", "")
    s = s.replace("""    private val mediaExtractorEngine: MediaExtractorEngine,
    private val rewardedAdManager: StartIoRewardedAdManager = StartIoRewardedAdManager()
""", """    private val mediaExtractorEngine: MediaExtractorEngine
""")
    a = s.find("    fun dismissAdErrorDialog() {")
    b = s.find("    fun openSiteInBrowser(url: String) {", a)
    if a < 0 or b < 0:
        raise SystemExit("Could not locate rewarded-ad ViewModel flow")
    direct = """    fun startSelectedDownload() {
        val state = _downloadOptionsState.value
        val request = state.pendingRequest ?: return
        val quality = request.qualities.getOrNull(state.selectedQualityIndex)
            ?: request.qualities.firstOrNull()
        if (quality == null) {
            _snackbarMessage.value = "لم يعثر المحلل على صيغة تنزيل صالحة لهذا الرابط"
            return
        }
        _downloadOptionsState.update { it.copy(pendingRequest = null) }
        viewModelScope.launch {
            val result = downloadRepository.enqueueDownload(request, quality)
            result.onSuccess {
                _snackbarMessage.value = "بدأ تنزيل ${request.title}"
            }.onFailure { err ->
                _snackbarMessage.value = "تعذر بدء التحميل: ${err.localizedMessage ?: "خطأ غير معروف"}"
            }
        }
    }

"""
    s = s[:a] + direct + s[b:]
    return s
edit("app/src/main/java/com/example/ui/MainViewModel.kt", viewmodel)

# MainActivity: remove rewarded-ad dialogs and use the new format chooser.
def activity(s):
    for line in [
        "import com.example.ui.components.AdFailureDialog\n",
        "import com.example.ui.components.AdLoadingOverlayDialog\n",
        "import com.example.ui.components.RewardDownloadConfirmDialog\n"
    ]:
        s = s.replace(line, "")
    s = s.replace("import com.example.ui.components.InAppVideoPlayerDialog\n",
                  "import com.example.ui.components.InAppVideoPlayerDialog\nimport com.example.ui.components.DownloadOptionsDialog\n")
    s = s.replace("    activity: ComponentActivity,\n    viewModel: MainViewModel\n",
                  "    viewModel: MainViewModel\n")
    s = s.replace("                    activity = this,\n                    viewModel = mainViewModel\n",
                  "                    viewModel = mainViewModel\n")
    s = s.replace("rewardDialogState", "downloadOptionsState")
    s = s.replace("viewModel.rewardDialogState", "viewModel.downloadOptionsState")
    a = s.find("    // 1. AlertDialog shown when Download button is tapped")
    b = s.find("    // 4. Built-in Video Player Modal", a)
    if a < 0 or b < 0:
        raise SystemExit("Could not locate MainActivity rewarded-ad dialog section")
    block = """    val pending = downloadOptionsState.pendingRequest
    if (pending != null) {
        DownloadOptionsDialog(
            pendingRequest = pending,
            selectedQualityIndex = downloadOptionsState.selectedQualityIndex,
            onSelectQuality = viewModel::selectQualityIndex,
            onConfirmDownload = viewModel::startSelectedDownload,
            onDismiss = viewModel::dismissDownloadOptionsDialog
        )
    }

"""
    return s[:a] + block + s[b:]
edit("app/src/main/java/com/example/MainActivity.kt", activity)

# Convert the old reward dialog into a clean format/quality chooser and remove ad-only overlays.
def dialogs(s):
    s = s.replace("fun RewardDownloadConfirmDialog(", "fun DownloadOptionsDialog(")
    s = s.replace("onConfirmWatchAd: () -> Unit", "onConfirmDownload: () -> Unit")
    s = s.replace("stringResource(R.string.reward_dialog_title)", "\"خيارات التنزيل\"")
    s = s.replace("stringResource(R.string.reward_dialog_message)",
                  "\"اختر الصيغة والجودة المتاحة لهذا الرابط. لن نعرض خيارات غير مؤكدة.\"")
    s = s.replace("onClick = onConfirmWatchAd", "onClick = onConfirmDownload")
    s = s.replace("confirm_reward_ad_button", "confirm_download_button")
    s = s.replace("cancel_reward_ad_button", "cancel_download_button")
    s = s.replace("stringResource(R.string.reward_dialog_confirm)", "\"ابدأ التنزيل\"")
    s = s.replace("stringResource(R.string.reward_dialog_cancel)", "\"إلغاء\"")
    a = s.find("@Composable\nfun AdLoadingOverlayDialog()")
    b = s.find("@Composable\nfun InAppVideoPlayerDialog(", a)
    if a >= 0 and b >= 0:
        s = s[:a] + s[b:]
    return s
edit("app/src/main/java/com/example/ui/components/MtaDialogs.kt", dialogs)

# Remove sample videos with fake titles/metadata and unrelated stock media URLs.
def catalog(s):
    a = s.find("    fun getFeaturedVideos(): List<VideoItem> = listOf(")
    b = s.find("\n    fun buildFromCapturedBrowserStreams(", a)
    if a < 0 or b < 0:
        raise SystemExit("Featured sample-video list not found")
    return s[:a] + "    // Do not fabricate recommendations: the feed contains only analyzed user links.\n    fun getFeaturedVideos(): List<VideoItem> = emptyList()\n" + s[b:]
edit("app/src/main/java/com/example/data/repository/VideoCatalogRepository.kt", catalog)

def home(s):
    s = s.replace('"مكتبة الفيديو الرئيسية"', '"المحتوى الذي تم تحليله"')
    s = s.replace('"\u0024{videos.size} فيديو متاح"', '"\u0024{videos.size} نتيجة مكتشفة"')
    s = s.replace('"لم يتم العثور على نتائج مطابقة"', '"لا توجد نتائج مكتشفة بعد"')
    s = s.replace('"يمكنك لصق رابط الفيديو مباشرة والضغط على زر تحليل للتحميل من أي موقع."', '"الصق رابطاً عاماً في شريط التحليل بالأعلى. ستظهر هنا النتائج التي يتم التحقق منها فعلياً، ولن نعرض فيديوهات تجريبية بروابط غير مرتبطة."')
    return s
edit("app/src/main/java/com/example/ui/screens/HomeScreen.kt", home)

# Rename repository API to remove the obsolete reward requirement.
def repo(s):
    s = s.replace("enqueueDownloadAfterReward", "enqueueDownload")
    s = s.replace("Page URLs are downloaded by the embedded yt-dlp engine. This path is called only from\n     * enqueueDownload(), after Start.io confirms the rewarded video was completed.",
                  "Page URLs are downloaded by the embedded yt-dlp engine after the user selects a format.")
    return s
edit("app/src/main/java/com/example/data/repository/DownloadRepository.kt", repo)

def strings(s):
    return re.sub(r"\s*<string name=\"reward_[^\"]+\">.*?</string>", "", s, flags=re.S)
edit("app/src/main/res/values/strings.xml", strings)

# Delete the complete ad SDK integration source so no dead ad code ships.
ads_dir = root / "app/src/main/java/com/example/ads"
if ads_dir.exists():
    import shutil
    shutil.rmtree(ads_dir)


# Update tests to assert the ad-free behavior rather than the removed Start.io SDK.
def tests(s):
    s = s.replace("fun `app name and StartIo App ID match MTA Downloader specification`() {",
                  "fun `app name and ad-free catalog match MTA Downloader specification`() {")
    s = s.replace('        assertEquals("210745939", MTADownloaderApp.STARTIO_APP_ID)\n', "")
    s = s.replace("assertTrue(repo.getFeaturedVideos().isNotEmpty())",
                  "assertTrue(repo.getFeaturedVideos().isEmpty())")
    return s
edit("app/src/test/java/com/example/ExampleRobolectricTest.kt", tests)

# Do not expose invented 1080p/720p choices as defaults; only the extractor may populate real streams.
def model(s):
    s = s.replace("val qualities: List<QualityOption> = defaultVideoQualities()",
                  "val qualities: List<QualityOption> = emptyList()")
    a = s.find("\nfun defaultVideoQualities(): List<QualityOption> = listOf(")
    if a >= 0:
        s = s[:a].rstrip() + "\n"
    return s
edit("app/src/main/java/com/example/data/model/VideoModels.kt", model)

def vm_import(s):
    return s.replace("import com.example.data.model.defaultVideoQualities\n", "")
edit("app/src/main/java/com/example/ui/MainViewModel.kt", vm_import)

# Offer honest automatic video/audio selectors for unresolved pages; do not invent resolutions.
def fallback(s):
    old = """                    qualities = listOf(
                        QualityOption(
                            id = "best",
                            label = "أفضل جودة متاحة",
                            format = "تلقائي",
                            sizeEstimate = "يحددها المحرك",
                            extension = "mp4",
                            mimeType = "video/mp4",
                            overrideStreamUrl = normalizedUrl
                        )
                    )"""
    new = """                    qualities = listOf(
                        QualityOption(
                            id = "best",
                            label = "أفضل فيديو متاح",
                            format = "اختيار تلقائي من المحرك",
                            sizeEstimate = "يحدد بعد التحليل",
                            extension = "mkv",
                            mimeType = "video/*",
                            overrideStreamUrl = normalizedUrl
                        ),
                        QualityOption(
                            id = "m4a",
                            label = "أفضل صوت متاح",
                            format = "صوت فقط • اختيار تلقائي",
                            sizeEstimate = "يحدد بعد التحليل",
                            extension = "m4a",
                            mimeType = "audio/mp4",
                            overrideStreamUrl = normalizedUrl
                        ),
                        QualityOption(
                            id = "subtitles",
                            label = "تنزيل الترجمات المتاحة",
                            format = "ترجمات VTT/SRT",
                            sizeEstimate = "يحدد بعد التحليل",
                            extension = "vtt",
                            mimeType = "text/vtt",
                            overrideStreamUrl = normalizedUrl
                        )
                    )"""
    if old not in s:
        raise SystemExit("Unresolved-page selector block not found")
    return s.replace(old, new, 1)
edit("app/src/main/java/com/example/data/extractor/MediaExtractorEngine.kt", fallback)

# Verify the Android source no longer contains ad SDK IDs, permissions, callbacks, or libraries.
scan_roots = [root / "app/src/main", root / "app/build.gradle.kts"]
patterns = re.compile(r"StartApp|StartIo|Start\.io|210745939|AD_ID|onVideoCompleted|com\.startapp|rewarded.?ad", re.I)
remaining = []
for base in scan_roots:
    files = [base] if base.is_file() else base.rglob("*")
    for f in files:
        if f.is_file() and f.suffix in {".kt", ".xml", ".kts"}:
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if patterns.search(line):
                    remaining.append(f"{f}:{n}:{line.strip()}")
if remaining:
    raise SystemExit("Ad-removal verification failed:\n" + "\n".join(remaining))
print("Applied ad-free download flow, removed fabricated recommendations, and passed source ad-reference scan.")
