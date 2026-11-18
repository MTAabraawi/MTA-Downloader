package com.example

import android.app.Application
import android.util.Log
import com.example.data.extractor.MediaExtractorEngine
import com.example.data.local.AppDatabase
import com.example.data.repository.DownloadRepository
import com.example.data.repository.VideoCatalogRepository
import com.startapp.sdk.adsbase.StartAppAd
import com.startapp.sdk.adsbase.StartAppSDK
import dev.ffmpegkit_maintained.ytdlp.YtDlp

class MTADownloaderApp : Application() {
    val database: AppDatabase by lazy { AppDatabase.getInstance(this) }
    val downloadRepository: DownloadRepository by lazy {
        DownloadRepository(applicationContext, database.downloadDao())
    }
    val videoCatalogRepository: VideoCatalogRepository by lazy { VideoCatalogRepository() }
    val mediaExtractorEngine: MediaExtractorEngine by lazy { MediaExtractorEngine(applicationContext) }

    override fun onCreate() {
        super.onCreate()
        // Initialize yt-dlp once; a failure is logged and reported when an extraction is attempted.
        runCatching { YtDlp.init(applicationContext) }
            .onFailure { Log.e("MTADownloader", "yt-dlp initialization failed", it) }

        // Preserve the existing Start.io app ID and initialization.
        StartAppSDK.initParams(this, STARTIO_APP_ID)
            .setReturnAdsEnabled(false)
            .init()
        StartAppAd.disableSplash()
    }

    companion object {
        const val STARTIO_APP_ID = "210745939"
    }
}
