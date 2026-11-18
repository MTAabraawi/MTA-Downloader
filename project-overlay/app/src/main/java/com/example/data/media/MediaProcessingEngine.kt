package com.example.data.media

import android.content.Context
import android.net.Uri
import androidx.annotation.WorkerThread
import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.ReturnCode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * On-device post-processing for media files already accessible to the app.
 * Arguments are passed as an argv array (not shell text) to avoid command injection.
 */
class MediaProcessingEngine(context: Context) {
    private val appContext = context.applicationContext

    suspend fun mergeSeparateAudioAndVideo(videoInput: Uri, audioInput: Uri, outputFile: File): Result<File> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(videoInput != Uri.EMPTY && audioInput != Uri.EMPTY) { "ملفات الإدخال غير صالحة" }
                val videoPath = copyToCache(videoInput, "mta-video-input")
                val audioPath = copyToCache(audioInput, "mta-audio-input")
                try { mergeFiles(videoPath, audioPath, outputFile).getOrThrow() }
                finally { videoPath.delete(); audioPath.delete() }
            }
        }

    /** Merge already-downloaded adaptive tracks without a second full-file copy. */
    suspend fun mergeFiles(videoInput: File, audioInput: File, outputFile: File): Result<File> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(videoInput.isFile && videoInput.length() > 0L) { "ملف الفيديو غير صالح أو فارغ" }
                require(audioInput.isFile && audioInput.length() > 0L) { "ملف الصوت غير صالح أو فارغ" }
                require(videoInput.canonicalFile != audioInput.canonicalFile) { "ملفا الإدخال يجب أن يكونا مختلفين" }
                val parent = outputFile.absoluteFile.parentFile
                require(parent != null && (parent.isDirectory || parent.mkdirs())) { "تعذر إنشاء مجلد الإخراج" }
                require(!outputFile.exists()) { "ملف الإخراج موجود مسبقاً" }
                val temporaryOutput = File(parent, outputFile.name + ".muxing")
                temporaryOutput.delete()
                try {
                    executeMux(videoInput.absolutePath, audioInput.absolutePath, temporaryOutput)
                    check(temporaryOutput.renameTo(outputFile)) { "تعذر اعتماد ملف الفيديو المدمج" }
                    check(outputFile.isFile && outputFile.length() > 0L) { "ملف الدمج النهائي غير صالح" }
                    outputFile
                } catch (error: Throwable) {
                    temporaryOutput.delete(); outputFile.delete(); throw error
                }
            }
        }

    @WorkerThread
    private fun executeMux(videoPath: String, audioPath: String, outputFile: File): File {
        val args = arrayOf("-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", videoPath, "-i", audioPath, "-map", "0:v:0", "-map", "1:a:0",
            "-c", "copy", "-shortest", "-f", "matroska", outputFile.absolutePath)
        val session = FFmpegKit.executeWithArguments(args)
        if (!ReturnCode.isSuccess(session.returnCode)) {
            outputFile.delete()
            throw IllegalStateException(session.failStackTrace?.takeIf { it.isNotBlank() }
                ?: session.allLogsAsString?.take(1200) ?: "فشل دمج مساري الصوت والفيديو")
        }
        check(outputFile.isFile && outputFile.length() > 0L) { "انتهى FFmpeg دون إنشاء ملف صالح" }
        return outputFile
    }

    private fun copyToCache(uri: Uri, prefix: String): File {
        val file = File.createTempFile(prefix, ".media", appContext.cacheDir)
        val input = appContext.contentResolver.openInputStream(uri)
            ?: throw IllegalArgumentException("تعذر فتح ملف الوسائط المحدد")
        input.use { source -> file.outputStream().use { output -> source.copyTo(output) } }
        check(file.length() > 0L) { "ملف الوسائط فارغ" }
        return file
    }
}
