package com.example.data.media

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.ReturnCode
import com.example.data.download.SegmentedHttpDownloader
import java.io.File
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import okio.Buffer
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Exercises the real HTTPS track downloader, then the packaged native FFmpeg muxer on-device. */
@RunWith(AndroidJUnit4::class)
class MediaProcessingEngineInstrumentedTest {
    @Test fun downloadsSeparateHttpsTracksAndMuxesThemIntoPlayableMatroska() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val work = File(context.cacheDir, "ffmpeg-download-integration-${System.nanoTime()}").apply { check(mkdirs()) }
        val videoFixture = File(work, "fixture-video.mp4")
        val audioFixture = File(work, "fixture-audio.m4a")
        val videoDownloaded = File(work, "downloaded-video.mp4")
        val audioDownloaded = File(work, "downloaded-audio.m4a")
        val merged = File(work, "merged.mkv")
        val held = HeldCertificate.Builder().addSubjectAlternativeName("localhost").build()
        val serverCertificates = HandshakeCertificates.Builder().heldCertificate(held).build()
        val clientCertificates = HandshakeCertificates.Builder().addTrustedCertificate(held.certificate).build()
        val server = MockWebServer()
        server.useHttps(serverCertificates.sslSocketFactory(), false)
        val client = OkHttpClient.Builder()
            .sslSocketFactory(clientCertificates.sslSocketFactory(), clientCertificates.trustManager)
            .hostnameVerifier { _, _ -> true }
            .build()
        try {
            val videoGeneration = FFmpegKit.executeWithArguments(arrayOf(
                "-nostdin", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:r=10:d=1",
                "-an", "-c:v", "mpeg4", "-q:v", "5", videoFixture.absolutePath
            ))
            assertTrue("Video fixture failed: ${videoGeneration.allLogsAsString}", ReturnCode.isSuccess(videoGeneration.returnCode))
            val audioGeneration = FFmpegKit.executeWithArguments(arrayOf(
                "-nostdin", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
                "-vn", "-c:a", "aac", audioFixture.absolutePath
            ))
            assertTrue("Audio fixture failed: ${audioGeneration.allLogsAsString}", ReturnCode.isSuccess(audioGeneration.returnCode))
            assertTrue(videoFixture.length() > 0L && audioFixture.length() > 0L)

            server.enqueue(MockResponse().setHeader("ETag", "\"video-v1\"")
                .setBody(Buffer().write(videoFixture.readBytes())))
            server.enqueue(MockResponse().setHeader("ETag", "\"audio-v1\"")
                .setBody(Buffer().write(audioFixture.readBytes())))
            server.start()
            val downloader = SegmentedHttpDownloader(client = client, publicHostValidator = { true })
            downloader.downloadToFile(server.url("/video").toString(), videoDownloaded)
            downloader.downloadToFile(server.url("/audio").toString(), audioDownloaded)
            assertTrue(videoDownloaded.length() == videoFixture.length())
            assertTrue(audioDownloaded.length() == audioFixture.length())

            val result = MediaProcessingEngine(context).mergeFiles(videoDownloaded, audioDownloaded, merged)
            assertTrue("Mux failed: ${result.exceptionOrNull()?.message}", result.isSuccess)
            assertTrue(merged.isFile && merged.length() > 0L)
            val verify = FFmpegKit.executeWithArguments(arrayOf(
                "-nostdin", "-v", "error", "-i", merged.absolutePath,
                "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"
            ))
            assertTrue("Merged file failed decoding: ${verify.allLogsAsString}", ReturnCode.isSuccess(verify.returnCode))
        } finally {
            runCatching { server.shutdown() }
            client.dispatcher.executorService.shutdown()
            client.connectionPool.evictAll()
            work.deleteRecursively()
        }
    }
}
