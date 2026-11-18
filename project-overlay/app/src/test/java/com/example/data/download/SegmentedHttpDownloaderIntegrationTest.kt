package com.example.data.download

import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import java.nio.file.Files

class SegmentedHttpDownloaderIntegrationTest {
    @Test
    fun downloadsAndAssemblesValidatedByteRanges() = runBlocking {
        val payload = ByteArray(37) { index -> (index * 7).toByte() }
        val client = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val request = chain.request()
                val range = request.header("Range") ?: "bytes=0-${payload.lastIndex}"
                val match = Regex("bytes=(\\d+)-(\\d+)").matchEntire(range)
                    ?: error("Unexpected range: $range")
                val start = match.groupValues[1].toInt()
                val end = match.groupValues[2].toInt()
                val bytes = payload.copyOfRange(start, end + 1)
                Response.Builder()
                    .request(request)
                    .protocol(Protocol.HTTP_1_1)
                    .code(206)
                    .message("Partial Content")
                    .header("Content-Range", "bytes $start-$end/${payload.size}")
                    .header("ETag", "\"mta-test-v1\"")
                    .body(bytes.toResponseBody("application/octet-stream".toMediaType()))
                    .build()
            }
            .build()

        val directory = Files.createTempDirectory("mta-segmented-test").toFile()
        try {
            val destination = File(directory, "sample.bin")
            val downloader = SegmentedHttpDownloader(
                client = client,
                segmentSize = 10L,
                parallelism = 3,
                minimumSegmentedSize = 1L
            )

            val result = downloader.downloadIfResumable(
                url = "https://media.example/sample.bin",
                destination = destination
            )

            assertEquals(destination, result)
            assertArrayEquals(payload, destination.readBytes())
            assertEquals(false, File(directory, "sample.bin.mta-resume").exists())
        } finally {
            directory.deleteRecursively()
        }
    }
}
