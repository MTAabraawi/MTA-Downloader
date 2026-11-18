package com.example.data.model

import androidx.annotation.DrawableRes

data class QualityOption(
    val id: String,
    val label: String,
    val format: String,
    val sizeEstimate: String,
    val extension: String,
    val mimeType: String,
    val overrideStreamUrl: String? = null,
    val requestHeaders: Map<String, String> = emptyMap(),
    val audioStreamUrl: String? = null,
    val audioRequestHeaders: Map<String, String> = emptyMap()
)

data class VideoItem(
    val id: String,
    val title: String,
    val channelName: String,
    val channelInitial: String,
    val views: String,
    val publishedAgo: String,
    val duration: String,
    val category: String,
    val sourcePlatform: String,
    @DrawableRes val thumbnailRes: Int? = null,
    val thumbnailUrl: String? = null,
    val streamUrl: String,
    val description: String,
    val qualities: List<QualityOption> = defaultVideoQualities()
)

data class SupportedSite(
    val id: String,
    val name: String,
    val url: String,
    val badgeColorHex: Long,
    val tag: String
)

enum class DownloadStatus {
    QUEUED,
    DOWNLOADING,
    PAUSED,
    COMPLETED,
    FAILED
}

data class PendingDownloadRequest(
    val title: String,
    val streamUrl: String,
    val sourcePlatform: String,
    val thumbnailUrl: String?,
    @DrawableRes val thumbnailRes: Int?,
    val qualities: List<QualityOption>
)

data class PlayerMedia(
    val title: String,
    val subtitle: String,
    val mediaUrl: String,
    val canDownload: Boolean = true,
    val sourceVideo: VideoItem? = null
)

data class DetectedMediaStream(
    val url: String,
    val title: String,
    val formatLabel: String,
    val extension: String,
    val mimeType: String,
    val requestHeaders: Map<String, String> = emptyMap(),
    val detectedAt: Long = System.currentTimeMillis()
)

fun defaultVideoQualities(): List<QualityOption> = listOf(
    QualityOption(
        id = "1080p",
        label = "1080p Full HD",
        format = "MP4",
        sizeEstimate = "HD",
        extension = "mp4",
        mimeType = "video/mp4"
    ),
    QualityOption(
        id = "720p",
        label = "720p HD",
        format = "MP4",
        sizeEstimate = "SD/HD",
        extension = "mp4",
        mimeType = "video/mp4"
    ),
    QualityOption(
        id = "360p",
        label = "360p SD",
        format = "MP4",
        sizeEstimate = "خفيف",
        extension = "mp4",
        mimeType = "video/mp4"
    ),
    QualityOption(
        id = "m4a",
        label = "صوت فقط",
        format = "M4A",
        sizeEstimate = "صوتي",
        extension = "m4a",
        mimeType = "audio/mp4"
    )
)
