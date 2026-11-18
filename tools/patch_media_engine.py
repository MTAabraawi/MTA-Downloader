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
gradle_text = gradle_properties.read_text(encoding="utf-8") if gradle_properties.exists() else ""
if "org.gradle.configuration-cache=" not in gradle_text:
    gradle_properties.write_text(
        gradle_text.rstrip() + "\norg.gradle.configuration-cache=false\n",
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



# Add a persisted pause state and a non-secret header snapshot for safe segmented resume.
def download_model(s):
    old = """enum class DownloadStatus {
    QUEUED,
    DOWNLOADING,
    COMPLETED,
    FAILED
}"""
    new = """enum class DownloadStatus {
    QUEUED,
    DOWNLOADING,
    PAUSED,
    COMPLETED,
    FAILED
}"""
    s = replace_required(s, old, new, "DownloadStatus paused state")
    old_field = """    val thumbnailResId: Int? = null,
    val createdAt: Long = System.currentTimeMillis()
)"""
    new_field = """    val thumbnailResId: Int? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val requestHeadersJson: String = ""
)"""
    return replace_required(s, old_field, new_field, "DownloadEntity request header snapshot")
edit("app/src/main/java/com/example/data/model/VideoModels.kt", download_model)
def room_entity_headers(s):
    s = s.replace("import androidx.room.Entity\n", "import androidx.room.ColumnInfo\nimport androidx.room.Entity\n")
    return replace_required(
        s,
        '    val requestHeadersJson: String = ""',
        '    @ColumnInfo(defaultValue = "\'\'") val requestHeadersJson: String = ""',
        "Room requestHeadersJson SQL default"
    )
edit("app/src/main/java/com/example/data/local/DownloadEntity.kt", room_entity_headers)


def database_migration(s):
    s = s.replace("import androidx.room.RoomDatabase\n",
                  "import androidx.room.RoomDatabase\nimport androidx.room.migration.Migration\nimport androidx.sqlite.db.SupportSQLiteDatabase\n")
    s = s.replace("    version = 1,", "    version = 2,")
    s = s.replace("    companion object {\n", """    companion object {
        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE downloads ADD COLUMN requestHeadersJson TEXT NOT NULL DEFAULT ''")
            }
        }

""")
    s = s.replace('''                    "mta_downloader.db"
                ).build().also { INSTANCE = it }''',
'''                    "mta_downloader.db"
                ).addMigrations(MIGRATION_1_2).build().also { INSTANCE = it }''')
    if "MIGRATION_1_2" not in s or "version = 2" not in s:
        raise SystemExit("Room v1-to-v2 migration could not be applied.")
    return s
edit("app/src/main/java/com/example/data/local/AppDatabase.kt", database_migration)


# Expose segmented pause/resume in the existing download manager UI.
def main_viewmodel_pause_resume(s):
    old = """    fun deleteDownload(entity: DownloadEntity) {
        viewModelScope.launch {
            downloadRepository.deleteDownload(entity)
            _snackbarMessage.value = "تم حذف الملف من القائمة"
        }
    }

"""
    new = """    fun deleteDownload(entity: DownloadEntity) {
        viewModelScope.launch {
            downloadRepository.deleteDownload(entity)
            _snackbarMessage.value = "تم حذف الملف من القائمة"
        }
    }

    fun pauseDownload(entity: DownloadEntity) {
        viewModelScope.launch {
            val paused = downloadRepository.pauseDownload(entity)
            _snackbarMessage.value = if (paused) "تم إيقاف التنزيل مؤقتاً" else "هذا التنزيل لا يدعم الإيقاف المؤقت"
        }
    }

    fun resumeDownload(entity: DownloadEntity) {
        viewModelScope.launch {
            val result = downloadRepository.resumeDownload(entity)
            result.onSuccess {
                _snackbarMessage.value = "تم استئناف التنزيل"
            }.onFailure { error ->
                _snackbarMessage.value = "تعذر استئناف التنزيل: " + (error.localizedMessage ?: "خطأ غير معروف")
            }
        }
    }

"""
    s = replace_required(s, old, new, "MainViewModel pause and resume actions")
    old_retry = """            mimeType = mimeType,
            overrideStreamUrl = entity.sourceUrl
        )"""
    new_retry = """            mimeType = mimeType,
            overrideStreamUrl = entity.sourceUrl,
            requestHeaders = downloadRepository.requestHeadersFor(entity)
        )"""
    return replace_required(s, old_retry, new_retry, "retry request headers")
edit("app/src/main/java/com/example/ui/MainViewModel.kt", main_viewmodel_pause_resume)

def main_activity_download_callbacks(s):
    old = """                                onRetryDownload = viewModel::retryDownload,
                                onDeleteDownload = viewModel::deleteDownload,
                                onExploreVideosClick = { navigateTopLevel(HomeRoute) }"""
    new = """                                onRetryDownload = viewModel::retryDownload,
                                onDeleteDownload = viewModel::deleteDownload,
                                onPauseDownload = viewModel::pauseDownload,
                                onResumeDownload = viewModel::resumeDownload,
                                onExploreVideosClick = { navigateTopLevel(HomeRoute) }"""
    return replace_required(s, old, new, "DownloadsScreen pause resume callbacks")
edit("app/src/main/java/com/example/MainActivity.kt", main_activity_download_callbacks)

def downloads_screen_pause_resume(s):
    s = s.replace(
        "import androidx.compose.material.icons.filled.PlayArrow\n",
        "import androidx.compose.material.icons.filled.PlayArrow\nimport androidx.compose.material.icons.filled.Pause\n"
    )
    s = s.replace(
        """    onDeleteDownload: (DownloadEntity) -> Unit,
    onExploreVideosClick: () -> Unit,""",
        """    onDeleteDownload: (DownloadEntity) -> Unit,
    onPauseDownload: (DownloadEntity) -> Unit,
    onResumeDownload: (DownloadEntity) -> Unit,
    onExploreVideosClick: () -> Unit,"""
    )
    s = s.replace(
        "it.status == DownloadStatus.DOWNLOADING.name || it.status == DownloadStatus.QUEUED.name",
        "it.status == DownloadStatus.DOWNLOADING.name || it.status == DownloadStatus.QUEUED.name || it.status == DownloadStatus.PAUSED.name",
        1
    )
    s = s.replace(
        """it.status == DownloadStatus.QUEUED.name ||
                    it.status == DownloadStatus.FAILED.name""",
        """it.status == DownloadStatus.QUEUED.name ||
                    it.status == DownloadStatus.PAUSED.name ||
                    it.status == DownloadStatus.FAILED.name"""
    )
    s = s.replace(
        'text = "$activeCount نشط • $completedCount مكتمل"',
        'text = "$activeCount نشط/متوقف • $completedCount مكتمل"'
    )
    s = s.replace(
        "                    onDeleteClick = { onDeleteDownload(item) }",
        """                    onDeleteClick = { onDeleteDownload(item) },
                    onPauseClick = { onPauseDownload(item) },
                    onResumeClick = { onResumeDownload(item) }"""
    )
    s = s.replace(
        """    onDeleteClick: () -> Unit
)""",
        """    onDeleteClick: () -> Unit,
    onPauseClick: () -> Unit,
    onResumeClick: () -> Unit
)"""
    )
    s = s.replace(
        """        DownloadStatus.FAILED -> MtaErrorRed
        else -> MtaNeonBlue""",
        """        DownloadStatus.FAILED -> MtaErrorRed
        DownloadStatus.PAUSED -> MtaTextSecondary
        else -> MtaNeonBlue"""
    )
    s = s.replace(
        """                            DownloadStatus.FAILED -> Icons.Filled.ErrorOutline
                            else -> Icons.Filled.CloudDownload""",
        """                            DownloadStatus.FAILED -> Icons.Filled.ErrorOutline
                            DownloadStatus.PAUSED -> Icons.Filled.Pause
                            else -> Icons.Filled.CloudDownload"""
    )
    s = s.replace(
        "if (status == DownloadStatus.DOWNLOADING || status == DownloadStatus.QUEUED)",
        "if (status == DownloadStatus.DOWNLOADING || status == DownloadStatus.QUEUED || status == DownloadStatus.PAUSED)"
    )
    s = s.replace(
        """                } else if (status == DownloadStatus.FAILED) {
                    "تعذر التحميل"
                } else {""",
        """                } else if (status == DownloadStatus.FAILED) {
                    "تعذر التحميل"
                } else if (status == DownloadStatus.PAUSED) {
                    "متوقف مؤقتاً"
                } else {"""
    )
    old = """                    DownloadStatus.FAILED -> {
                        Button(
                            onClick = onRetryClick,"""
    new = """                    DownloadStatus.PAUSED -> {
                        Button(
                            onClick = onResumeClick,
                            colors = ButtonDefaults.buttonColors(containerColor = MtaSurfaceElevated),
                            shape = RoundedCornerShape(10.dp),
                            contentPadding = PaddingValues(horizontal = 14.dp),
                            modifier = Modifier.height(40.dp)
                        ) {
                            Icon(imageVector = Icons.Filled.PlayArrow, contentDescription = null, tint = MtaCyanGlow)
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("استئناف", color = MtaCyanGlow)
                        }
                    }
                    DownloadStatus.DOWNLOADING -> {
                        if (item.systemDownloadId == 0L && item.totalBytes > 0L) {
                            IconButton(onClick = onPauseClick, modifier = Modifier.testTag("pause_download_" + item.id)) {
                                Icon(imageVector = Icons.Filled.Pause, contentDescription = "إيقاف مؤقت", tint = MtaCyanGlow)
                            }
                        }
                    }
                    DownloadStatus.QUEUED -> Unit
                    DownloadStatus.FAILED -> {
                        Button(
                            onClick = onRetryClick,"""
    s = replace_required(s, old, new, "DownloadsScreen pause and resume actions")
    return s
edit("app/src/main/java/com/example/ui/screens/DownloadsScreen.kt", downloads_screen_pause_resume)

# Carry only non-secret browser request context in memory; never persist cookies or authorization tokens.
def video_models_headers(s):
    old = """data class DetectedMediaStream(
    val url: String,
    val title: String,
    val formatLabel: String,
    val extension: String,
    val mimeType: String,
    val detectedAt: Long = System.currentTimeMillis()
)"""
    new = """data class DetectedMediaStream(
    val url: String,
    val title: String,
    val formatLabel: String,
    val extension: String,
    val mimeType: String,
    val requestHeaders: Map<String, String> = emptyMap(),
    val detectedAt: Long = System.currentTimeMillis()
)"""
    return replace_required(s, old, new, "DetectedMediaStream request headers")
edit("app/src/main/java/com/example/data/model/VideoModels.kt", video_models_headers)

def catalog_headers(s):
    s = s.replace(
        "import com.example.R\n",
        "import com.example.R\nimport com.example.data.extractor.BrowserMediaKind\nimport com.example.data.extractor.MediaExtractionRouter\n"
    )
    old = """    fun buildFromCapturedBrowserStreams(
        streams: List<DetectedMediaStream>,
        pageTitle: String,
        platform: String
    ): VideoItem {
        val primary = streams.first()
        val qualities = streams.mapIndexed { idx, s ->
            QualityOption(
                id = "captured_${idx}",
                label = if (idx == 0) "البث الملتقط الأساسي (${s.formatLabel})" else "بث ملتقط ${idx + 1} (${s.formatLabel})",
                format = s.formatLabel,
                sizeEstimate = "مباشر",
                extension = s.extension,
                mimeType = s.mimeType,
                overrideStreamUrl = s.url
            )
        }
        return VideoItem(
            id = "captured_${System.currentTimeMillis()}",
            title = pageTitle.ifBlank { primary.title },
            channelName = platform,
            channelInitial = platform.firstOrNull()?.uppercase() ?: "M",
            views = "${streams.size} مسار مكتشف",
            publishedAgo = "الآن",
            duration = primary.formatLabel,
            category = "رائج الآن",
            sourcePlatform = platform,
            thumbnailRes = R.drawable.img_hero_banner,
            streamUrl = primary.url,
            description = "تم التقاط بث الوسائط مباشرة من المتصفح الذكي.",
            qualities = qualities
        )
    }"""
    new = """    fun buildFromCapturedBrowserStreams(
        streams: List<DetectedMediaStream>,
        pageTitle: String,
        platform: String
    ): VideoItem {
        val parsed = streams.mapIndexedNotNull { idx, stream ->
            val media = MediaExtractionRouter.classifyBrowserMedia(stream.url, stream.mimeType)
                ?: return@mapIndexedNotNull null
            val isManifest = media.kind == BrowserMediaKind.HLS_MANIFEST ||
                media.kind == BrowserMediaKind.DASH_MANIFEST
            val extension = when (media.kind) {
                BrowserMediaKind.HLS_MANIFEST -> "m3u8"
                BrowserMediaKind.DASH_MANIFEST -> "mpd"
                else -> stream.extension
            }
            val label = when (media.kind) {
                BrowserMediaKind.HLS_MANIFEST -> "بث HLS"
                BrowserMediaKind.DASH_MANIFEST -> "بث DASH"
                BrowserMediaKind.AUDIO_FILE -> "صوت مباشر"
                BrowserMediaKind.VIDEO_FILE -> "فيديو مباشر"
            }
            stream to QualityOption(
                id = if (isManifest) "captured_manifest_" + idx else "captured_" + idx,
                label = label + " • " + stream.formatLabel,
                format = label,
                sizeEstimate = if (isManifest) "بث متكيف" else "مباشر",
                extension = extension,
                mimeType = media.mimeType,
                overrideStreamUrl = media.url,
                requestHeaders = stream.requestHeaders
            )
        }
        val primary = parsed.firstOrNull()?.first ?: streams.first()
        val qualities = parsed.map { it.second }
        return VideoItem(
            id = "captured_" + System.currentTimeMillis(),
            title = pageTitle.ifBlank { primary.title },
            channelName = platform,
            channelInitial = platform.firstOrNull()?.uppercase() ?: "M",
            views = qualities.size.toString() + " مسار مكتشف",
            publishedAgo = "الآن",
            duration = primary.formatLabel,
            category = "رائج الآن",
            sourcePlatform = platform,
            thumbnailRes = R.drawable.img_hero_banner,
            streamUrl = parsed.firstOrNull()?.first?.url ?: primary.url,
            description = "تم التقاط بث الوسائط مباشرة من المتصفح الذكي.",
            qualities = qualities
        )
    }"""
    return replace_required(s, old, new, "browser media manifest classification")
edit("app/src/main/java/com/example/data/repository/VideoCatalogRepository.kt", catalog_headers)

def browser_headers(s):
    s = s.replace(
        "onMediaDetected: (String, String?, String?) -> Unit,",
        "onMediaDetected: (String, String?, String?, Map<String, String>) -> Unit,"
    )
    s = s.replace("onMediaDetected(src, title, mime)", "onMediaDetected(src, title, mime, emptyMap())")
    s = s.replace("onMediaDetected(url, title, mimetype)", "onMediaDetected(url, title, mimetype, emptyMap())")
    old = """                                    if (lower.endsWith(".mp4") ||
                                        lower.endsWith(".m4v") ||
                                        lower.endsWith(".webm") ||
                                        lower.endsWith(".mov") ||
                                        lower.endsWith(".mp3") ||
                                        lower.endsWith(".m4a") ||
                                        accept.contains("video/", true)
                                    ) {
                                        post { onMediaDetected(reqUrl, view?.title, null, request?.requestHeaders.orEmpty()) }
                                    }"""
    new = """                                    val manifestMime = when {
                                        accept.contains("mpegurl", true) -> "application/vnd.apple.mpegurl"
                                        accept.contains("dash+xml", true) -> "application/dash+xml"
                                        else -> null
                                    }
                                    if (lower.endsWith(".mp4") ||
                                        lower.endsWith(".m4v") ||
                                        lower.endsWith(".webm") ||
                                        lower.endsWith(".mov") ||
                                        lower.endsWith(".mp3") ||
                                        lower.endsWith(".m4a") ||
                                        lower.endsWith(".m3u8") ||
                                        lower.endsWith(".mpd") ||
                                        manifestMime != null ||
                                        accept.contains("video/", true)
                                    ) {
                                        post {
                                            onMediaDetected(
                                                reqUrl,
                                                view?.title,
                                                manifestMime,
                                                request?.requestHeaders.orEmpty()
                                            )
                                        }
                                    }"""
    return replace_required(s, old, new, "capture HLS/DASH manifests and browser headers")
edit("app/src/main/java/com/example/ui/screens/BrowserScreen.kt", browser_headers)

def viewmodel_headers(s):
    s = s.replace(
        """        if (lower.endsWith(".ts") || lower.endsWith(".m4s") || lower.endsWith(".m3u8") || lower.endsWith(".mpd")) return""",
        """        if (lower.endsWith(".ts") || lower.endsWith(".m4s")) return"""
    )
    old_ext = """        val ext = when {
            lower.endsWith(".mp3") || mimeHint?.contains("audio/mpeg", true) == true -> "mp3"
            lower.endsWith(".m4a") || mimeHint?.contains("audio/mp4", true) == true -> "m4a"
            lower.endsWith(".webm") || mimeHint?.contains("video/webm", true) == true -> "webm"
            lower.endsWith(".mov") || mimeHint?.contains("quicktime", true) == true -> "mov"
            else -> "mp4"
        }
        val formatLabel = ext.uppercase(Locale.US)
        val mime = when {
            isAudio && ext == "m4a" -> "audio/mp4"
            isAudio -> "audio/mpeg"
            ext == "mov" -> "video/quicktime"
            else -> "video/$ext"
        }"""
    new_ext = """        val ext = when {
            lower.endsWith(".m3u8") || mimeHint?.contains("mpegurl", true) == true -> "m3u8"
            lower.endsWith(".mpd") || mimeHint?.contains("dash+xml", true) == true -> "mpd"
            lower.endsWith(".mp3") || mimeHint?.contains("audio/mpeg", true) == true -> "mp3"
            lower.endsWith(".m4a") || mimeHint?.contains("audio/mp4", true) == true -> "m4a"
            lower.endsWith(".webm") || mimeHint?.contains("video/webm", true) == true -> "webm"
            lower.endsWith(".mov") || mimeHint?.contains("quicktime", true) == true -> "mov"
            else -> "mp4"
        }
        val formatLabel = when (ext) {
            "m3u8" -> "HLS"
            "mpd" -> "DASH"
            else -> ext.uppercase(Locale.US)
        }
        val mime = when {
            ext == "m3u8" -> "application/vnd.apple.mpegurl"
            ext == "mpd" -> "application/dash+xml"
            isAudio && ext == "m4a" -> "audio/mp4"
            isAudio -> "audio/mpeg"
            ext == "mov" -> "video/quicktime"
            else -> "video/$ext"
        }"""
    s = replace_required(s, old_ext, new_ext, "browser HLS/DASH media metadata")
    old_headers = """        _browserState.update { state ->
            if (state.detectedStreams.any { it.url == mediaUrl }) {"""
    new_headers = """        // Do not retain Cookie, Authorization, or other credential-bearing headers.
        val allowedHeaders = setOf("referer", "origin", "user-agent", "accept", "accept-language")
        val safeHeaders = requestHeaders.entries.mapNotNull { (name, value) ->
            val normalized = name.lowercase(Locale.US)
            if (normalized in allowedHeaders && value.length <= 2048 &&
                !value.contains('\\r') && !value.contains('\\n')) name to value else null
        }.toMap()

        _browserState.update { state ->
            if (state.detectedStreams.any { it.url == mediaUrl }) {"""
    s = replace_required(s, old_headers, new_headers, "browser safe header filtering")
    old_stream = """                    extension = ext,
                    mimeType = mime
"""
    new_stream = """                    extension = ext,
                    mimeType = mime,
                    requestHeaders = safeHeaders
"""
    return replace_required(s, old_stream, new_stream, "captured stream request headers")
edit("app/src/main/java/com/example/ui/MainViewModel.kt", viewmodel_headers)

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
