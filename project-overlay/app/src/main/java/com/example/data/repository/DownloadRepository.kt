package com.example.data.repository

import android.app.DownloadManager
import android.content.Context
import android.content.ContentValues
import android.os.Build
import android.provider.MediaStore
import android.net.Uri
import android.os.Environment
import com.example.data.local.DownloadDao
import com.example.data.local.DownloadEntity
import com.example.data.model.DownloadStatus
import com.example.data.model.PendingDownloadRequest
import com.example.data.model.QualityOption
import dev.ffmpegkit_maintained.ytdlp.DownloadProgressCallback
import dev.ffmpegkit_maintained.ytdlp.YtDlp
import dev.ffmpegkit_maintained.ytdlp.YtDlpRequest
import java.io.File
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext

class DownloadRepository(
    private val context: Context,
    private val downloadDao: DownloadDao
) {
    private val downloadManager: DownloadManager by lazy {
        context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
    }

    val allDownloads: Flow<List<DownloadEntity>> = downloadDao.observeAllDownloads()

    suspend fun enqueueDownloadAfterReward(
        request: PendingDownloadRequest,
        quality: QualityOption
    ): Result<Long> = withContext(Dispatchers.IO) {
        runCatching {
            val targetStreamUrl = quality.overrideStreamUrl?.takeIf { it.isNotBlank() } ?: request.streamUrl
            if (!isDirectMediaUrl(targetStreamUrl)) {
                return@runCatching downloadWithYtDlp(request, quality, targetStreamUrl)
            }

            val sanitizedName = request.title
                .replace(Regex("[^a-zA-Z0-9\\u0600-\\u06FF._ -]"), "_")
                .trim()
                .take(48)
                .ifBlank { "mta_video_${System.currentTimeMillis()}" }
            val fileName = "${sanitizedName}_${quality.id}.${quality.extension}"

            val dmRequest = DownloadManager.Request(Uri.parse(targetStreamUrl)).apply {
                setTitle(request.title)
                setDescription("MTA Downloader • ${quality.label}")
                setMimeType(quality.mimeType)
                setAllowedOverMetered(true)
                setAllowedOverRoaming(true)
                setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                setDestinationInExternalPublicDir(
                    Environment.DIRECTORY_DOWNLOADS,
                    "MTA_Downloader/$fileName"
                )
            }

            val systemId = downloadManager.enqueue(dmRequest)
            val entity = DownloadEntity(
                systemDownloadId = systemId,
                title = request.title,
                sourceUrl = targetStreamUrl,
                sourcePlatform = request.sourcePlatform,
                qualityLabel = quality.label,
                format = quality.format,
                fileName = fileName,
                status = DownloadStatus.DOWNLOADING.name,
                progress = 0,
                thumbnailUrl = request.thumbnailUrl,
                thumbnailResId = request.thumbnailRes
            )
            downloadDao.insert(entity)
        }
    }

    private fun isDirectMediaUrl(url: String): Boolean {
        val path = Uri.parse(url).lastPathSegment.orEmpty().lowercase()
        return listOf(".mp4", ".m4v", ".webm", ".mov", ".mp3", ".m4a", ".aac", ".wav", ".ogg")
            .any(path::endsWith)
    }

    /**
     * Page URLs are downloaded by the embedded yt-dlp engine. This path is called only from
     * enqueueDownloadAfterReward(), after Start.io confirms the rewarded video was completed.
     */
    private suspend fun downloadWithYtDlp(
        request: PendingDownloadRequest,
        quality: QualityOption,
        pageUrl: String
    ): Long {
        val downloadsRoot = requireNotNull(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)) {
            "مساحة التخزين غير متاحة"
        }
        val outputDir = File(downloadsRoot, "MTA_Downloader")
        check(outputDir.exists() || outputDir.mkdirs()) { "تعذر إنشاء مجلد التنزيلات" }
        val startedAt = System.currentTimeMillis()
        val safeTitle = request.title
            .replace(Regex("[^a-zA-Z0-9\\u0600-\\u06FF._ -]"), "_")
            .trim().take(60).ifBlank { "mta_video" }
        val outputTemplate = File(outputDir, "${safeTitle}_%(id)s.%(ext)s").absolutePath
        val formatSelector = when {
            quality.id.contains("1080") -> "best[height<=1080]/best"
            quality.id.contains("720") -> "best[height<=720]/best"
            quality.id.contains("480") -> "best[height<=480]/best"
            quality.id.contains("360") -> "best[height<=360]/best"
            quality.id.equals("m4a", true) || quality.mimeType.startsWith("audio/") ->
                "bestaudio[ext=m4a]/bestaudio"
            else -> "best"
        }
        val entityId = downloadDao.insert(
            DownloadEntity(
                systemDownloadId = 0L,
                title = request.title,
                sourceUrl = pageUrl,
                sourcePlatform = request.sourcePlatform,
                qualityLabel = quality.label,
                format = quality.format,
                fileName = "$safeTitle.pending",
                status = DownloadStatus.DOWNLOADING.name,
                progress = 0,
                thumbnailUrl = request.thumbnailUrl,
                thumbnailResId = request.thumbnailRes
            )
        )
        val ytdlpRequest = YtDlpRequest(pageUrl)
            .setOutputTemplate(outputTemplate)
            .addOption("--no-playlist")
            .addOption("--no-warnings")
            .addOption("--newline")
            .addOption("-f", formatSelector)
        val progressScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        val lastUpdate = AtomicLong(0L)
        val future = YtDlp.executeAsync(
            ytdlpRequest,
            DownloadProgressCallback { progress, _, _ ->
                val now = System.currentTimeMillis()
                if (now - lastUpdate.get() >= 900L && lastUpdate.getAndSet(now) <= now) {
                    val percent = progress.toInt().coerceIn(0, 99)
                    progressScope.launch {
                        // Update the existing Room row while the extractor reports progress.
                        downloadDao.update(
                            DownloadEntity(
                                id = entityId,
                                systemDownloadId = 0L,
                                title = request.title,
                                sourceUrl = pageUrl,
                                sourcePlatform = request.sourcePlatform,
                                qualityLabel = quality.label,
                                format = quality.format,
                                fileName = "$safeTitle.pending",
                                status = DownloadStatus.DOWNLOADING.name,
                                progress = percent,
                                thumbnailUrl = request.thumbnailUrl,
                                thumbnailResId = request.thumbnailRes
                            )
                        )
                    }
                }
            }
        )
        try {
            val response = runInterruptible(Dispatchers.IO) {
                future.get(45, TimeUnit.MINUTES)
            }
            check(response.isSuccess) {
                "yt-dlp تعذر استخراج/تنزيل الوسائط (رمز ${response.exitCode})"
            }
        } catch (error: Throwable) {
            future.cancel(true)
            downloadDao.getActiveDownloads().firstOrNull { it.id == entityId }?.let {
                downloadDao.update(it.copy(status = DownloadStatus.FAILED.name))
            }
            throw error
        } finally {
            progressScope.cancel()
        }

        val outputFile = outputDir.listFiles()
            ?.filter { it.isFile && it.length() > 0L && it.lastModified() >= startedAt - 2_000L }
            ?.maxByOrNull { it.lastModified() }
            ?: error("انتهى محرك التنزيل دون العثور على ملف ناتج")
        val publicUri = publishToDownloads(outputFile, request.title)
        val completed = downloadDao.getActiveDownloads().firstOrNull { it.id == entityId }
            ?: error("تعذر العثور على سجل التنزيل")
        downloadDao.update(
            completed.copy(
                format = outputFile.extension.uppercase(),
                fileName = outputFile.name,
                localUri = publicUri.toString(),
                status = DownloadStatus.COMPLETED.name,
                progress = 100,
                downloadedBytes = outputFile.length(),
                totalBytes = outputFile.length()
            )
        )
        if (publicUri.scheme == "content") outputFile.delete()
        return entityId
    }

    private fun publishToDownloads(source: File, title: String): Uri {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            return Uri.fromFile(source)
        }
        val mime = when (source.extension.lowercase()) {
            "mp4", "m4v" -> "video/mp4"
            "webm" -> "video/webm"
            "mp3" -> "audio/mpeg"
            "m4a" -> "audio/mp4"
            "opus" -> "audio/opus"
            "mkv" -> "video/x-matroska"
            else -> "application/octet-stream"
        }
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, source.name)
            put(MediaStore.MediaColumns.MIME_TYPE, mime)
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/MTA_Downloader")
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        val collection = MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        val destination = requireNotNull(context.contentResolver.insert(collection, values)) {
            "تعذر إنشاء ملف في مجلد التنزيلات"
        }
        try {
            context.contentResolver.openOutputStream(destination, "w").use { output ->
                requireNotNull(output) { "تعذر فتح ملف التنزيلات" }
                source.inputStream().use { input -> input.copyTo(output) }
            }
            val ready = ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }
            context.contentResolver.update(destination, ready, null, null)
            return destination
        } catch (error: Throwable) {
            context.contentResolver.delete(destination, null, null)
            throw error
        }
    }

    suspend fun syncActiveDownloadsProgress(): Boolean = withContext(Dispatchers.IO) {
        val active = downloadDao.getActiveDownloads()
        if (active.isEmpty()) return@withContext false

        val ids = active.map { it.systemDownloadId }.filter { it > 0L }.toLongArray()
        if (ids.isEmpty()) return@withContext false

        val query = DownloadManager.Query().setFilterById(*ids)
        val cursor = downloadManager.query(query)
        val updatedIds = mutableSetOf<Long>()

        cursor?.use { c ->
            val idIdx = c.getColumnIndex(DownloadManager.COLUMN_ID)
            val statusIdx = c.getColumnIndex(DownloadManager.COLUMN_STATUS)
            val bytesIdx = c.getColumnIndex(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)
            val totalIdx = c.getColumnIndex(DownloadManager.COLUMN_TOTAL_SIZE_BYTES)
            val localUriIdx = c.getColumnIndex(DownloadManager.COLUMN_LOCAL_URI)

            while (c.moveToNext()) {
                val sysId = if (idIdx >= 0) c.getLong(idIdx) else continue
                updatedIds.add(sysId)
                val entity = active.firstOrNull { it.systemDownloadId == sysId } ?: continue

                val dmStatus = if (statusIdx >= 0) c.getInt(statusIdx) else DownloadManager.STATUS_RUNNING
                val downloaded = if (bytesIdx >= 0) c.getLong(bytesIdx).coerceAtLeast(0L) else 0L
                val total = if (totalIdx >= 0) c.getLong(totalIdx).coerceAtLeast(0L) else 0L
                val localUri = if (localUriIdx >= 0) c.getString(localUriIdx) else entity.localUri

                val mappedStatus = when (dmStatus) {
                    DownloadManager.STATUS_SUCCESSFUL -> DownloadStatus.COMPLETED
                    DownloadManager.STATUS_FAILED -> DownloadStatus.FAILED
                    DownloadManager.STATUS_PENDING -> DownloadStatus.QUEUED
                    else -> DownloadStatus.DOWNLOADING
                }
                val progress = when {
                    mappedStatus == DownloadStatus.COMPLETED -> 100
                    total > 0L -> ((downloaded * 100L) / total).toInt().coerceIn(0, 99)
                    else -> entity.progress
                }
                downloadDao.update(
                    entity.copy(
                        status = mappedStatus.name,
                        progress = progress,
                        downloadedBytes = downloaded,
                        totalBytes = total,
                        localUri = localUri
                    )
                )
            }
        }

        for (entity in active) {
            if (entity.systemDownloadId !in updatedIds) {
                downloadDao.update(entity.copy(status = DownloadStatus.FAILED.name))
            }
        }
        true
    }

    suspend fun deleteDownload(entity: DownloadEntity) = withContext(Dispatchers.IO) {
        if (entity.systemDownloadId > 0L) {
            runCatching { downloadManager.remove(entity.systemDownloadId) }
        } else {
            entity.localUri?.let { uri ->
                runCatching {
                    val parsed = Uri.parse(uri)
                    if (parsed.scheme == "content") context.contentResolver.delete(parsed, null, null)
                    else if (parsed.scheme == "file") File(parsed.path.orEmpty()).delete()
                }
            }
        }
        downloadDao.deleteById(entity.id)
    }
}
