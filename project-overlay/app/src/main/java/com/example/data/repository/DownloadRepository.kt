package com.example.data.repository

import android.app.DownloadManager
import android.content.Context
import android.content.ContentValues
import android.os.Build
import android.provider.MediaStore
import android.net.Uri
import android.os.Environment
import com.example.data.download.SegmentedHttpDownloader
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
import java.util.concurrent.ConcurrentHashMap
import org.json.JSONObject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.async
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit

class DownloadRepository(
    private val context: Context,
    private val downloadDao: DownloadDao
) {
    private val segmentedDownloader by lazy { SegmentedHttpDownloader() }
    private val segmentedScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val segmentedJobs = ConcurrentHashMap<Long, Deferred<File?>>()
    private val segmentedSemaphore = Semaphore(2)

    private val downloadManager: DownloadManager by lazy {
        context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
    }

    val allDownloads: Flow<List<DownloadEntity>> = downloadDao.observeAllDownloads()

    suspend fun enqueueDownload(
        request: PendingDownloadRequest,
        quality: QualityOption,
        resumeEntity: DownloadEntity? = null
    ): Result<Long> = withContext(Dispatchers.IO) {
        runCatching {
            val targetStreamUrl = quality.overrideStreamUrl?.takeIf { it.isNotBlank() } ?: request.streamUrl
            validateDownloadUrl(targetStreamUrl)
            if (resumeEntity == null && !isDirectMediaUrl(targetStreamUrl) &&
                !quality.id.startsWith("newpipe_") && !quality.id.startsWith("captured_")) {
                return@runCatching downloadWithYtDlp(request, quality, targetStreamUrl)
            }

            val sanitizedName = request.title
                .replace(Regex("[^a-zA-Z0-9\\u0600-\\u06FF._ -]"), "_")
                .trim()
                .take(48)
                .ifBlank { "mta_video_${System.currentTimeMillis()}" }
            val fileName = resumeEntity?.fileName ?: "${sanitizedName}_${quality.id}.${quality.extension}"

            val entity = resumeEntity?.copy(
                systemDownloadId = 0L,
                sourceUrl = targetStreamUrl,
                sourcePlatform = request.sourcePlatform,
                qualityLabel = quality.label,
                format = quality.format,
                status = DownloadStatus.DOWNLOADING.name,
                progress = 0,
                localUri = null,
                requestHeadersJson = encodeRequestHeaders(quality.requestHeaders)
            ) ?: DownloadEntity(
                systemDownloadId = 0L,
                title = request.title,
                sourceUrl = targetStreamUrl,
                sourcePlatform = request.sourcePlatform,
                qualityLabel = quality.label,
                format = quality.format,
                fileName = fileName,
                status = DownloadStatus.DOWNLOADING.name,
                progress = 0,
                thumbnailUrl = request.thumbnailUrl,
                thumbnailResId = request.thumbnailRes,
                requestHeadersJson = encodeRequestHeaders(quality.requestHeaders)
            )
            val entityId = if (resumeEntity != null) {
                downloadDao.update(entity)
                resumeEntity.id
            } else {
                downloadDao.insert(entity)
            }
            val trackedEntity = entity.copy(id = entityId)
            val appDownloads = requireNotNull(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)) {
                "مساحة التخزين غير متاحة"
            }
            val segmentedDirectory = File(appDownloads, "MTA_Downloader")
            check(segmentedDirectory.exists() || segmentedDirectory.mkdirs()) { "تعذر إنشاء مجلد التنزيلات" }
            val segmentedTarget = File(segmentedDirectory, fileName)
            val progressScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
            val lastProgressAt = AtomicLong(0L)
            downloadDao.update(trackedEntity.copy(status = DownloadStatus.QUEUED.name))
            val segmentedTask = segmentedScope.async {
                segmentedSemaphore.withPermit {
                    downloadDao.update(trackedEntity.copy(status = DownloadStatus.DOWNLOADING.name))
                    segmentedDownloader.downloadIfResumable(
                        targetStreamUrl,
                        segmentedTarget,
                        headers = safeRequestHeaders(quality.requestHeaders)
                    ) { progress ->
                        val now = System.currentTimeMillis()
                        if (now - lastProgressAt.get() >= 800L && lastProgressAt.getAndSet(now) <= now) {
                            progressScope.launch {
                                downloadDao.update(
                                    trackedEntity.copy(
                                        progress = if (progress.totalBytes > 0L)
                                            ((progress.downloadedBytes * 100L) / progress.totalBytes).toInt().coerceIn(0, 99)
                                        else 0,
                                        downloadedBytes = progress.downloadedBytes,
                                        totalBytes = progress.totalBytes
                                    )
                                )
                            }
                        }
                    }
                }
            }
            segmentedJobs[entityId] = segmentedTask
            val segmentedFile = try {
                segmentedTask.await()
            } catch (cancelled: CancellationException) {
                progressScope.cancel()
                downloadDao.update(trackedEntity.copy(status = DownloadStatus.PAUSED.name))
                return@runCatching entityId
            } catch (error: Throwable) {
                progressScope.cancel()
                downloadDao.update(trackedEntity.copy(status = DownloadStatus.FAILED.name))
                throw error
            } finally {
                segmentedJobs.remove(entityId, segmentedTask)
            }

            if (segmentedFile != null) {
                progressScope.cancel()
                val publicUri = publishToDownloads(segmentedFile, request.title)
                downloadDao.update(
                    trackedEntity.copy(
                        format = segmentedFile.extension.uppercase(),
                        fileName = segmentedFile.name,
                        localUri = publicUri.toString(),
                        status = DownloadStatus.COMPLETED.name,
                        progress = 100,
                        downloadedBytes = segmentedFile.length(),
                        totalBytes = segmentedFile.length()
                    )
                )
                if (publicUri.scheme == "content") segmentedFile.delete()
                return@runCatching entityId
            }
            progressScope.cancel()
            if (resumeEntity != null) cleanupSegmentedFiles(fileName)

            val dmRequest = DownloadManager.Request(Uri.parse(targetStreamUrl)).apply {
                setTitle(request.title)
                setDescription("MTA Downloader • " + quality.label)
                setMimeType(quality.mimeType)
                setAllowedOverMetered(true)
                setAllowedOverRoaming(true)
                setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                safeRequestHeaders(quality.requestHeaders).forEach { (name, value) -> addRequestHeader(name, value) }
                setDestinationInExternalPublicDir(
                    Environment.DIRECTORY_DOWNLOADS,
                    "MTA_Downloader/" + fileName
                )
            }

            val systemId = downloadManager.enqueue(dmRequest)
            downloadDao.update(
                trackedEntity.copy(
                    systemDownloadId = systemId,
                    status = DownloadStatus.DOWNLOADING.name
                )
            )
            entityId
        }
    }

    private fun encodeRequestHeaders(headers: Map<String, String>): String {
        val persistent = safeRequestHeaders(headers).mapValues { (name, value) ->
            if (name.equals("Referer", ignoreCase = true)) {
                runCatching {
                    Uri.parse(value).buildUpon().clearQuery().fragment(null).build().toString()
                }.getOrDefault(value.substringBefore("?").substringBefore("#"))
            } else value
        }
        return JSONObject(persistent).toString()
    }

    fun requestHeadersFor(entity: DownloadEntity): Map<String, String> =
        decodeRequestHeaders(entity.requestHeadersJson)

    private fun decodeRequestHeaders(encoded: String): Map<String, String> = runCatching {
        val json = JSONObject(encoded)
        json.keys().asSequence().associateWith { key -> json.getString(key) }
    }.getOrDefault(emptyMap())

    suspend fun pauseDownload(entity: DownloadEntity): Boolean = withContext(Dispatchers.IO) {
        val task = segmentedJobs[entity.id] ?: return@withContext false
        if (!task.isActive) return@withContext false
        task.cancel(CancellationException("Paused by user"))
        task.join()
        downloadDao.update(entity.copy(status = DownloadStatus.PAUSED.name))
        true
    }

    suspend fun resumeDownload(entity: DownloadEntity): Result<Long> = withContext(Dispatchers.IO) {
        runCatching {
            require(entity.status == DownloadStatus.PAUSED.name) { "التنزيل ليس متوقفاً مؤقتاً" }
            val extension = entity.fileName.substringAfterLast('.', entity.format.lowercase())
                .lowercase().filter { it.isLetterOrDigit() }.ifBlank { "mp4" }
            val mime = when (extension) {
                "mp3" -> "audio/mpeg"
                "m4a", "aac" -> "audio/mp4"
                "webm" -> "video/webm"
                "mov" -> "video/quicktime"
                "mkv" -> "video/x-matroska"
                "vtt" -> "text/vtt"
                "srt" -> "application/x-subrip"
                else -> "video/mp4"
            }
            val headers = decodeRequestHeaders(entity.requestHeadersJson)
            val quality = QualityOption(
                id = "newpipe_resume",
                label = entity.qualityLabel,
                format = entity.format,
                sizeEstimate = "استئناف التنزيل",
                extension = extension,
                mimeType = mime,
                overrideStreamUrl = entity.sourceUrl,
                requestHeaders = headers
            )
            val request = PendingDownloadRequest(
                title = entity.title,
                streamUrl = entity.sourceUrl,
                sourcePlatform = entity.sourcePlatform,
                thumbnailUrl = entity.thumbnailUrl,
                thumbnailRes = entity.thumbnailResId,
                qualities = listOf(quality)
            )
            enqueueDownload(request, quality, resumeEntity = entity).getOrThrow()
        }
    }

    private fun safeRequestHeaders(headers: Map<String, String>): Map<String, String> {
        val allowed = setOf("referer", "origin", "user-agent", "accept", "accept-language")
        return headers.filter { (name, value) ->
            name.lowercase(Locale.US) in allowed &&
                value.length <= 2048 &&
                !value.contains('\r') &&
                !value.contains('\n')
        }
    }

    /**
     * Accept only absolute HTTPS URLs with a public-looking host. This prevents accidental
     * handling of file/content/javascript schemes, embedded credentials, and obvious local hosts.
     */
    private fun validateDownloadUrl(rawUrl: String) {
        val uri = Uri.parse(rawUrl.trim())
        require(uri.scheme.equals("https", ignoreCase = true)) {
            "لأسباب أمنية، يجب أن يبدأ رابط التنزيل بـ HTTPS"
        }
        val host = uri.host?.lowercase()?.trimEnd('.')
        require(!host.isNullOrBlank()) { "رابط التنزيل لا يحتوي على اسم مضيف صالح" }
        require(uri.userInfo == null) { "الروابط التي تحتوي بيانات دخول مضمّنة غير مسموحة" }
        require(host != "localhost" && !host.endsWith(".localhost") && !host.endsWith(".local")) {
            "لا يمكن تنزيل روابط الأجهزة أو الشبكات المحلية"
        }
        if (host.matches(Regex("""\d{1,3}(\.\d{1,3}){3}"""))) {
            val octets = host.split(".").map { it.toIntOrNull() ?: 256 }
            require(octets.size == 4 && octets.all { it in 0..255 }) { "عنوان IP غير صالح" }
            val a = octets[0]
            val b = octets[1]
            val isPrivateOrReserved = a == 0 || a == 10 || a == 127 ||
                (a == 169 && b == 254) || (a == 172 && b in 16..31) ||
                (a == 192 && b == 168) || a >= 224
            require(!isPrivateOrReserved) { "لا يمكن تنزيل روابط عناوين IP الخاصة أو المحجوزة" }
        }
    }

    private fun isDirectMediaUrl(url: String): Boolean {
        val path = Uri.parse(url).lastPathSegment.orEmpty().lowercase()
        return listOf(".mp4", ".m4v", ".webm", ".mov", ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".vtt", ".srt", ".ttml", ".srv1", ".srv2", ".srv3")
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
        val isPlaylist = Uri.parse(pageUrl).getQueryParameter("list")?.isNotBlank() == true ||
            Uri.parse(pageUrl).path.orEmpty().contains("/playlist", ignoreCase = true) ||
            Uri.parse(pageUrl).path.orEmpty().contains("/showcase/", ignoreCase = true)
        val outputTemplate = if (isPlaylist) {
            File(outputDir, safeTitle + "/%(playlist_index)03d - %(title).80s [%(id)s].%(ext)s").absolutePath
        } else {
            File(outputDir, safeTitle + "_%(id)s.%(ext)s").absolutePath
        }
        val formatSelector = when {
            quality.id == "subtitles" -> "best"
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
                thumbnailResId = request.thumbnailRes,
                requestHeadersJson = encodeRequestHeaders(quality.requestHeaders)
            )
        )
        val ytdlpRequest = YtDlpRequest(pageUrl)
            .setOutputTemplate(outputTemplate)
            .addOption(if (isPlaylist) "--yes-playlist" else "--no-playlist")
            .addOption("--no-warnings")
            .addOption("--newline")
            .addOption("-f", formatSelector)
        if (quality.id == "subtitles") {
            ytdlpRequest
                .addOption("--skip-download")
                .addOption("--write-subs")
                .addOption("--write-auto-subs")
                .addOption("--sub-langs", "all")
                .addOption("--sub-format", "vtt/best")
        }
        safeRequestHeaders(quality.requestHeaders).forEach { (name, value) ->
            ytdlpRequest.addOption("--add-header", name + ": " + value)
        }
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
                                thumbnailResId = request.thumbnailRes,
                                requestHeadersJson = encodeRequestHeaders(quality.requestHeaders)
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

        val mediaExtensions = setOf(
            "mp4", "m4v", "webm", "mov", "mkv", "mp3", "m4a", "aac", "wav", "ogg", "opus", "flv", "ts", "vtt", "srt", "ttml", "srv1", "srv2", "srv3"
        )
        val outputFiles = outputDir.walkTopDown()
            .filter {
                it.isFile && it.length() > 0L &&
                    it.lastModified() >= startedAt - 2_000L &&
                    it.extension.lowercase() in mediaExtensions
            }
            .sortedBy { it.lastModified() }
            .toList()
        check(outputFiles.isNotEmpty()) { "انتهى محرك التنزيل دون العثور على ملفات وسائط ناتجة" }

        outputFiles.forEachIndexed { index, outputFile ->
            val itemTitle = if (isPlaylist) {
                outputFile.nameWithoutExtension.substringAfter(" - ", outputFile.nameWithoutExtension)
            } else request.title
            val publicUri = publishToDownloads(outputFile, itemTitle)
            if (index == 0) {
                val completed = downloadDao.getActiveDownloads().firstOrNull { it.id == entityId }
                    ?: error("تعذر العثور على سجل التنزيل")
                downloadDao.update(
                    completed.copy(
                        title = itemTitle,
                        format = outputFile.extension.uppercase(),
                        fileName = outputFile.name,
                        localUri = publicUri.toString(),
                        status = DownloadStatus.COMPLETED.name,
                        progress = 100,
                        downloadedBytes = outputFile.length(),
                        totalBytes = outputFile.length()
                    )
                )
            } else {
                downloadDao.insert(
                    DownloadEntity(
                        systemDownloadId = 0L,
                        title = itemTitle,
                        sourceUrl = pageUrl,
                        sourcePlatform = request.sourcePlatform,
                        qualityLabel = quality.label,
                        format = outputFile.extension.uppercase(),
                        fileName = outputFile.name,
                        status = DownloadStatus.COMPLETED.name,
                        progress = 100,
                        thumbnailUrl = request.thumbnailUrl,
                        thumbnailResId = request.thumbnailRes,
                        localUri = publicUri.toString(),
                        requestHeadersJson = encodeRequestHeaders(quality.requestHeaders),
                        downloadedBytes = outputFile.length(),
                        totalBytes = outputFile.length()
                    )
                )
            }
            if (publicUri.scheme == "content") outputFile.delete()
        }
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
            "vtt" -> "text/vtt"
            "srt" -> "application/x-subrip"
            "ttml" -> "application/ttml+xml"
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

        // A process restart drops in-memory jobs; completed segments remain on disk and can resume.
        val interruptedSegments = active.filter {
            it.systemDownloadId == 0L &&
                (it.totalBytes > 0L || it.status == DownloadStatus.QUEUED.name) &&
                segmentedJobs[it.id]?.isActive != true
        }
        interruptedSegments.forEach { downloadDao.update(it.copy(status = DownloadStatus.PAUSED.name)) }

        val ids = active.map { it.systemDownloadId }.filter { it > 0L }.toLongArray()
        if (ids.isEmpty()) return@withContext interruptedSegments.isNotEmpty()

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
            // Local yt-dlp jobs use systemDownloadId=0 and are not tracked by Android DownloadManager.
            if (entity.systemDownloadId > 0L && entity.systemDownloadId !in updatedIds) {
                downloadDao.update(entity.copy(status = DownloadStatus.FAILED.name))
            }
        }
        true
    }

    suspend fun deleteDownload(entity: DownloadEntity) = withContext(Dispatchers.IO) {
        segmentedJobs.remove(entity.id)?.let { task ->
            task.cancel(CancellationException("Download deleted"))
            task.join()
        }
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
        cleanupSegmentedFiles(entity.fileName)
        downloadDao.deleteById(entity.id)
    }

    private fun cleanupSegmentedFiles(fileName: String) {
        val root = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS) ?: return
        val directory = File(root, "MTA_Downloader")
        listOf(
            fileName + ".mta-resume",
            fileName + ".mta-resume.tmp",
            fileName + ".mta-assembling"
        ).forEach { File(directory, it).delete() }
        directory.listFiles()?.filter { it.name.startsWith(fileName + ".mta-part-") }?.forEach { it.delete() }
    }
}
