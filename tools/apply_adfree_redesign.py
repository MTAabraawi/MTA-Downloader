from pathlib import Path
import re, sys
root = Path(sys.argv[1])
def edit(path, fn):
    p = root / path
    s = p.read_text(encoding="utf-8")
    out = fn(s)
    if out != s:
        p.write_text(out, encoding="utf-8")

def main_vm(s):
    s=s.replace("import android.app.Activity\n","").replace("import com.example.ads.StartIoRewardedAdManager\n","").replace("import com.example.data.model.defaultVideoQualities\n","")
    s=s.replace("""data class RewardDialogState(
    val pendingRequest: PendingDownloadRequest? = null,
    val selectedQualityIndex: Int = 0,
    val isLoadingAd: Boolean = false,
    val adErrorMessage: String? = null,
    val lastAttemptedRequest: PendingDownloadRequest? = null,
    val lastAttemptedQuality: QualityOption? = null
)""","""data class DownloadOptionsState(
    val pendingRequest: PendingDownloadRequest? = null,
    val selectedQualityIndex: Int = 0
)""")
    s=s.replace("""    private val mediaExtractorEngine: MediaExtractorEngine,
    private val rewardedAdManager: StartIoRewardedAdManager = StartIoRewardedAdManager()
""","""    private val mediaExtractorEngine: MediaExtractorEngine
""")
    s=s.replace("_rewardDialogState","_downloadOptionsState").replace("rewardDialogState","downloadOptionsState").replace("RewardDialogState","DownloadOptionsState")
    a=s.index("    fun dismissRewardConfirmationDialog()")
    b=s.index("    fun openSiteInBrowser(",a)
    block="""    fun dismissDownloadOptionsDialog() {
        _downloadOptionsState.update { it.copy(pendingRequest = null) }
    }

    fun confirmDownload() {
        val state = _downloadOptionsState.value
        val request = state.pendingRequest ?: return
        val quality = request.qualities.getOrNull(state.selectedQualityIndex) ?: request.qualities.firstOrNull()
        if (quality == null) {
            _snackbarMessage.value = "لم يعثر المحلل على صيغة تنزيل صالحة لهذا الرابط"
            return
        }
        _downloadOptionsState.update { it.copy(pendingRequest = null) }
        viewModelScope.launch {
            val result = downloadRepository.enqueueDownload(request, quality)
            result.onSuccess { _snackbarMessage.value = "بدأ تنزيل ${request.title}" }
                .onFailure { err -> _snackbarMessage.value = "تعذر بدء التحميل: ${err.localizedMessage ?: "خطأ غير معروف"}" }
        }
    }

"""
    s=s[:a]+block+s[b:]
    return s
edit("app/src/main/java/com/example/ui/MainViewModel.kt",main_vm)
edit("app/src/main/java/com/example/data/repository/DownloadRepository.kt",lambda s:s.replace("enqueueDownloadAfterReward","enqueueDownload").replace("""    /**
     * Page URLs are downloaded by the embedded yt-dlp engine. This path is called only from
     * enqueueDownload(), after Start.io confirms the rewarded video was completed.
     */""","""    /** Page URLs are handled by the embedded on-device yt-dlp engine. */"""))
def app(s):
    s=s.replace("import com.startapp.sdk.adsbase.StartAppAd\n","").replace("import com.startapp.sdk.adsbase.StartAppSDK\n","")
    s=re.sub(r"\n        // Preserve the existing Start\.io app ID and initialization\..*?const val STARTIO_APP_ID = \"210745939\"\n    }\n", "\n", s, flags=re.S)
    return s
edit("app/src/main/java/com/example/MTADownloaderApp.kt",app)
edit("app/src/main/AndroidManifest.xml",lambda s:s.replace('    <uses-permission android:name="com.google.android.gms.permission.AD_ID" />\n','').replace('''        <meta-data
            android:name="com.startapp.sdk.APPLICATION_ID"
            android:value="210745939" />

''',''))
edit("app/build.gradle.kts",lambda s:s.replace('  // Start.io rewarded ads are intentionally preserved.\n  implementation("com.startapp:inapp-sdk:5.+")\n',''))
edit("app/src/main/java/com/example/data/extractor/MediaExtractorEngine.kt",lambda s:s.replace("// The rewarded-ad gate remains in MainViewModel before the repository starts.","// Unresolved public page URLs are handled by the on-device yt-dlp engine.").replace("سيحاول محرك yt-dlp المحلي استخراج الوسائط بعد إكمال إعلان المكافأة. قد لا تدعم بعض الروابط أو قد تفرض المنصة قيوداً على الوصول.","سيحاول محرك yt-dlp المحلي استخراج الوسائط العامة. قد لا تدعم بعض الروابط أو قد تفرض المنصة قيوداً على الوصول."))
def catalog(s):
    a=s.index("    fun getFeaturedVideos(): List<VideoItem> = listOf(")
    b=s.index("\n    fun buildFromCapturedBrowserStreams(",a)
    return s[:a]+"    // No fabricated trending feed: display only media discovered from a user-supplied URL.\n    fun getFeaturedVideos(): List<VideoItem> = emptyList()\n"+s[b:]
edit("app/src/main/java/com/example/data/repository/VideoCatalogRepository.kt",catalog)
def dialogs(s):
    s=s.replace("fun RewardDownloadConfirmDialog(","fun DownloadOptionsDialog(").replace("onConfirmWatchAd: () -> Unit,","onConfirmDownload: () -> Unit,").replace("stringResource(R.string.reward_dialog_title)",'"خيارات التنزيل"').replace("stringResource(R.string.reward_dialog_message)",'"اختر أحد المسارات المتاحة ثم ابدأ التنزيل مباشرة دون إعلانات."').replace("onClick = onConfirmWatchAd,","onClick = onConfirmDownload,").replace('"confirm_reward_ad_button"','"confirm_download_button"').replace("stringResource(R.string.reward_dialog_confirm)",'"تنزيل الآن"').replace('"cancel_reward_ad_button"','"cancel_download_button"').replace("stringResource(R.string.reward_dialog_cancel)",'"إلغاء"')
    a=s.find("@Composable\nfun AdLoadingOverlayDialog()")
    if a!=-1:
        b=s.find("@Composable\nfun InAppVideoPlayerDialog(",a)
        if b==-1: raise SystemExit("Cannot locate player dialog boundary")
        s=s[:a]+s[b:]
    return s
edit("app/src/main/java/com/example/ui/components/MtaDialogs.kt",dialogs)
def activity(s):
    s=s.replace("import com.example.ui.components.AdFailureDialog\n","").replace("import com.example.ui.components.AdLoadingOverlayDialog\n","").replace("import com.example.ui.components.RewardDownloadConfirmDialog\n","import com.example.ui.components.DownloadOptionsDialog\n")
    s=s.replace("val rewardDialogState by viewModel.rewardDialogState.collectAsStateWithLifecycle()","val downloadOptionsState by viewModel.downloadOptionsState.collectAsStateWithLifecycle()")
    a=s.index("    // 1. AlertDialog shown when Download button is tapped")
    b=s.index("    // 4. Built-in Video Player Modal",a)
    repl="""    // Direct download flow; there is no advertising gate.
    val pending = downloadOptionsState.pendingRequest
    if (pending != null) {
        DownloadOptionsDialog(
            pendingRequest = pending,
            selectedQualityIndex = downloadOptionsState.selectedQualityIndex,
            onSelectQuality = viewModel::selectQualityIndex,
            onConfirmDownload = viewModel::confirmDownload,
            onDismiss = viewModel::dismissDownloadOptionsDialog
        )
    }

"""
    return s[:a]+repl+s[b:]
edit("app/src/main/java/com/example/MainActivity.kt",activity)
def strings(s):
    return re.sub(r'^.*name="reward_dialog_(?:title|message|confirm|cancel)".*\n','',s,flags=re.M)
edit("app/src/main/res/values/strings.xml",strings)
ads=root/"app/src/main/java/com/example/ads"
if ads.exists():
    import shutil; shutil.rmtree(ads)
print("Ad-free source transformation completed")


# Remove the obsolete ad implementation package so no orphan SDK imports can break compilation.
ads_dir = root / "app/src/main/java/com/example/ads"
if ads_dir.exists():
    import shutil
    shutil.rmtree(ads_dir)

print("Ad-free source transformation completed; final invariant is checked after the overlay is applied.")
