package com.example.data.download

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.InetAddress
import java.io.IOException
import java.util.Properties
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

data class SegmentedDownloadProgress(
    val downloadedBytes: Long,
    val totalBytes: Long,
    val completedSegments: Int,
    val totalSegments: Int
)

/**
 * XDM-style bounded parallel downloader for large files.
 * Returns null when the origin does not support validated byte ranges; callers should then use
 * Android DownloadManager. Completed segments survive cancellation and are resumed on retry.
 */
class SegmentedHttpDownloader(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build(),
    private val segmentSize: Long = 8L * 1024L * 1024L,
    private val parallelism: Int = 4
) {
    suspend fun downloadIfResumable(
        url: String,
        destination: File,
        headers: Map<String, String> = emptyMap(),
        onProgress: (SegmentedDownloadProgress) -> Unit = {}
    ): File? = withContext(Dispatchers.IO) {
        require(url.startsWith("https://", true)) { "Only HTTPS downloads are supported" }
        val probe = probe(url, headers) ?: return@withContext null
        if (!probe.rangeSupported || probe.total <= 16L * 1024L * 1024L || probe.validator.isNullOrBlank()) {
            return@withContext null
        }
        val parent = destination.absoluteFile.parentFile ?: return@withContext null
        check(parent.exists() || parent.mkdirs()) { "Could not create download directory" }

        val count = ((probe.total + segmentSize - 1L) / segmentSize).toInt()
        val checkpoint = File(parent, destination.name + ".mta-resume")
        val parts = (0 until count).map { File(parent, destination.name + ".mta-part-" + it) }
        val completed = loadCheckpoint(checkpoint, url, probe, count).filterTo(mutableSetOf()) { index ->
            parts[index].isFile && parts[index].length() == expectedLength(index, probe.total)
        }
        parts.forEachIndexed { index, file -> if (index !in completed) file.delete() }
        val checkpointLock = Any()
        saveCheckpoint(checkpoint, url, probe, completed)

        val downloaded = AtomicLong(completed.sumOf { expectedLength(it, probe.total) })
        onProgress(SegmentedDownloadProgress(downloaded.get(), probe.total, completed.size, count))

        coroutineScope {
            (0 until count).filterNot { it in completed }.chunked(parallelism).forEach { batch ->
                currentCoroutineContext().ensureActive()
                batch.map { index ->
                    async(Dispatchers.IO) {
                        downloadSegment(url, headers, probe, index, parts[index])
                        synchronized(checkpointLock) {
                            completed.add(index)
                            saveCheckpoint(checkpoint, url, probe, completed)
                        }
                        onProgress(
                            SegmentedDownloadProgress(
                                downloaded.addAndGet(expectedLength(index, probe.total)),
                                probe.total,
                                completed.size,
                                count
                            )
                        )
                    }
                }.awaitAll()
            }
        }

        currentCoroutineContext().ensureActive()
        val assembled = File(parent, destination.name + ".mta-assembling")
        assembled.delete()
        FileOutputStream(assembled).use { output ->
            parts.forEach { part ->
                FileInputStream(part).use { input -> input.copyTo(output) }
            }
        }
        check(assembled.length() == probe.total) { "Assembled file size does not match the origin" }
        if (destination.exists()) check(destination.delete()) { "Could not replace destination" }
        check(assembled.renameTo(destination)) { "Could not finalize segmented download" }
        parts.forEach { it.delete() }
        checkpoint.delete()
        destination
    }


    /** Full HTTPS transfer for adaptive tracks. A validator-backed partial file survives pause/cancel. */
    suspend fun downloadToFile(url: String, destination: File, headers: Map<String, String> = emptyMap(),
        onProgress: (SegmentedDownloadProgress) -> Unit = {}): File = withContext(Dispatchers.IO) {
        require(url.startsWith("https://", true)) { "Only HTTPS downloads are supported" }
        val parent = destination.absoluteFile.parentFile ?: throw IOException("Missing destination directory")
        check(parent.exists() || parent.mkdirs()) { "Could not create download directory" }
        val temporary = File(parent, destination.name + ".download-part")
        val metadata = File(parent, destination.name + ".download-meta")
        var offset = temporary.takeIf { it.isFile }?.length() ?: 0L
        var validator: String? = null
        var expectedTotal = -1L
        if (offset > 0L && metadata.isFile) {
            runCatching {
                val saved = Properties().apply { metadata.inputStream().use(::load) }
                require(saved.getProperty("url") == url)
                validator = saved.getProperty("validator")?.takeIf { it.isNotBlank() }
                expectedTotal = saved.getProperty("total")?.toLongOrNull() ?: -1L
                require(validator != null && expectedTotal > offset)
            }.onFailure {
                temporary.delete(); metadata.delete(); offset = 0L; validator = null; expectedTotal = -1L
            }
        } else if (offset > 0L) {
            temporary.delete(); metadata.delete(); offset = 0L
        }
        val request = Request.Builder().url(url).get().apply {
            if (offset > 0L && validator != null) {
                header("Range", "bytes=$offset-")
                header("If-Range", validator!!)
            }
            headers.forEach { (name, value) -> header(name, value) }
        }.build()
        val call = client.newCall(request)
        val cancellation = currentCoroutineContext()[Job]?.invokeOnCompletion { cause ->
            if (cause is CancellationException) call.cancel()
        }
        try {
            call.execute().use { response ->
                if (response.code == 416) {
                    temporary.delete(); metadata.delete()
                    throw IOException("Media server rejected the resume offset; retry the download")
                }
                check(response.isSuccessful) { "Media server returned HTTP ${response.code}" }
                val finalUrl = response.request.url
                check(finalUrl.isHttps && isPublicHost(finalUrl.host)) { "Redirect resolved to an insecure or private host" }
                val contentType = response.header("Content-Type").orEmpty().substringBefore(';').trim()
                check(!contentType.equals("text/html", true) && !contentType.contains("json", true)) {
                    "Media URL returned a page or JSON instead of media"
                }
                val body = response.body ?: throw IOException("Media response body is empty")
                val responseValidator = response.header("ETag")?.takeIf { it.isNotBlank() }
                    ?: response.header("Last-Modified")?.takeIf { it.isNotBlank() }
                val append = offset > 0L && response.code == 206 && responseValidator == validator
                if (offset > 0L && response.code == 206) {
                    val range = parseContentRange(response.header("Content-Range"))
                    if (!append || range == null || range.first != offset || range.third <= offset) {
                        temporary.delete(); metadata.delete()
                        throw IOException("Media server changed the stream while resuming")
                    }
                    expectedTotal = range.third
                } else {
                    offset = 0L
                    expectedTotal = body.contentLength()
                    validator = responseValidator
                    temporary.delete()
                }
                if (validator != null) {
                    val props = Properties().apply {
                        setProperty("url", url)
                        setProperty("validator", validator!!)
                        setProperty("total", expectedTotal.toString())
                    }
                    FileOutputStream(metadata).use { props.store(it, "MTA adaptive stream resume") }
                } else metadata.delete()
                var downloaded = offset
                FileOutputStream(temporary, append).use { output ->
                    body.byteStream().use { input ->
                        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                        while (true) {
                            currentCoroutineContext().ensureActive()
                            val count = input.read(buffer)
                            if (count < 0) break
                            output.write(buffer, 0, count)
                            downloaded += count
                            onProgress(SegmentedDownloadProgress(downloaded, expectedTotal, 0, 1))
                        }
                        output.fd.sync()
                    }
                }
                check(downloaded > offset) { "Media stream is empty" }
                if (expectedTotal > 0L) check(downloaded == expectedTotal) { "Media transfer was truncated" }
            }
            currentCoroutineContext().ensureActive()
            if (destination.exists()) check(destination.delete()) { "Could not replace destination" }
            check(temporary.renameTo(destination)) { "Could not finalize media file" }
            metadata.delete()
            destination
        } catch (error: Throwable) {
            if (validator == null || !temporary.isFile || temporary.length() <= 0L) {
                temporary.delete(); metadata.delete()
            }
            throw error
        } finally { cancellation?.dispose() }
    }

    private fun isPublicHost(host: String): Boolean = runCatching {
        val normalized = host.lowercase().trimEnd('.')
        if (normalized == "localhost" || normalized.endsWith(".localhost") || normalized.endsWith(".local")) return@runCatching false
        InetAddress.getAllByName(normalized).all { address ->
            !address.isAnyLocalAddress && !address.isLoopbackAddress && !address.isLinkLocalAddress &&
                !address.isSiteLocalAddress && !address.isMulticastAddress
        }
    }.getOrDefault(false)

    private data class Probe(
        val total: Long,
        val etag: String?,
        val modified: String?,
        val rangeSupported: Boolean
    ) {
        val validator: String? get() = etag?.takeIf(String::isNotBlank)
            ?: modified?.takeIf(String::isNotBlank)
    }

    private fun probe(url: String, headers: Map<String, String>): Probe? {
        val request = Request.Builder().url(url).get().header("Range", "bytes=0-0").apply {
            headers.forEach { (key, value) -> header(key, value) }
        }.build()
        client.newCall(request).execute().use { response ->
            val range = parseContentRange(response.header("Content-Range"))
            val total = range?.third ?: -1L
            return Probe(
                total,
                response.header("ETag"),
                response.header("Last-Modified"),
                response.code == 206 && range != null && range.first == 0L && range.second == 0L
            )
        }
    }

    private suspend fun downloadSegment(
        url: String,
        headers: Map<String, String>,
        probe: Probe,
        index: Int,
        destination: File
    ) {
        val start = index.toLong() * segmentSize
        val end = minOf(probe.total - 1L, start + segmentSize - 1L)
        var failure: Throwable? = null
        repeat(3) { attempt ->
            currentCoroutineContext().ensureActive()
            destination.delete()
            val requestBuilder = Request.Builder().url(url).get().header("Range", "bytes=" + start + "-" + end)
            probe.validator?.let { requestBuilder.header("If-Range", it) }
            headers.forEach { (key, value) -> requestBuilder.header(key, value) }
            val call = client.newCall(requestBuilder.build())
            val job = currentCoroutineContext()[Job]
            val cancellation = job?.invokeOnCompletion { cause ->
                if (cause is CancellationException) call.cancel()
            }
            try {
                call.execute().use { response ->
                    check(response.code == 206) { "Origin did not honor byte range" }
                    val range = parseContentRange(response.header("Content-Range"))
                        ?: error("Invalid Content-Range response")
                    check(range.first == start && range.second == end && range.third == probe.total) {
                        "Origin returned a mismatched byte range"
                    }
                    val body = response.body ?: error("Empty segment response")
                    FileOutputStream(destination).use { output ->
                        body.byteStream().use { input ->
                            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                            while (true) {
                                currentCoroutineContext().ensureActive()
                                val read = input.read(buffer)
                                if (read < 0) break
                                output.write(buffer, 0, read)
                            }
                        }
                    }
                }
                check(destination.length() == expectedLength(index, probe.total)) {
                    "Segment length does not match requested range"
                }
                return
            } catch (error: Throwable) {
                failure = error
                destination.delete()
                if (error is CancellationException) throw error
                if (attempt < 2) kotlinx.coroutines.delay(300L * (attempt + 1))
            } finally {
                cancellation?.dispose()
            }
        }
        throw failure ?: IOException("Segment download failed")
    }

    private fun loadCheckpoint(file: File, url: String, probe: Probe, count: Int): Set<Int> {
        if (!file.isFile) return emptySet()
        return runCatching {
            val properties = Properties().apply { file.inputStream().use(::load) }
            val matches = properties.getProperty("url") == url &&
                properties.getProperty("validator") == probe.validator &&
                properties.getProperty("total") == probe.total.toString() &&
                properties.getProperty("segmentSize") == segmentSize.toString()
            if (!matches) {
                file.delete()
                emptySet()
            } else {
                properties.getProperty("completed").orEmpty()
                    .split(',').mapNotNull { it.toIntOrNull() }.filter { it in 0 until count }.toSet()
            }
        }.getOrElse {
            file.delete()
            emptySet()
        }
    }

    private fun saveCheckpoint(file: File, url: String, probe: Probe, completed: Set<Int>) {
        val properties = Properties().apply {
            setProperty("url", url)
            setProperty("validator", probe.validator.orEmpty())
            setProperty("total", probe.total.toString())
            setProperty("segmentSize", segmentSize.toString())
            setProperty("completed", completed.sorted().joinToString(","))
        }
        val temporary = File(file.parentFile, file.name + ".tmp")
        FileOutputStream(temporary).use { properties.store(it, "MTA Downloader resume data") }
        if (file.exists()) file.delete()
        check(temporary.renameTo(file)) { "Could not save resume checkpoint" }
    }

    private fun expectedLength(index: Int, total: Long): Long {
        val start = index.toLong() * segmentSize
        return minOf(total - 1L, start + segmentSize - 1L) - start + 1L
    }

    internal fun parseContentRange(value: String?): Triple<Long, Long, Long>? {
        val match = Regex("""bytes\s+(\d+)-(\d+)/(\d+)""", RegexOption.IGNORE_CASE)
            .matchEntire(value?.trim().orEmpty()) ?: return null
        val start = match.groupValues[1].toLongOrNull() ?: return null
        val end = match.groupValues[2].toLongOrNull() ?: return null
        val total = match.groupValues[3].toLongOrNull() ?: return null
        return if (start <= end && end < total) Triple(start, end, total) else null
    }
}
