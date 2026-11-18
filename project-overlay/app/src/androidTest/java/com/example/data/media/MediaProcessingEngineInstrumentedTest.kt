package com.example.data.media
import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.ReturnCode
import java.io.File
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Runs packaged FFmpeg native binaries on-device, not a mocked command planner. */
@RunWith(AndroidJUnit4::class)
class MediaProcessingEngineInstrumentedTest {
 @Test fun muxesSeparatelyDownloadedVideoAndAudioIntoPlayableMatroska() = runBlocking {
  val context:Context = InstrumentationRegistry.getInstrumentation().targetContext
  val work=File(context.cacheDir,"ffmpeg-integration-${System.nanoTime()}").apply { check(mkdirs()) }
  val video=File(work,"video-only.mp4"); val audio=File(work,"audio-only.m4a"); val merged=File(work,"merged.mkv")
  try {
   val videoGeneration=FFmpegKit.executeWithArguments(arrayOf("-nostdin","-y","-f","lavfi","-i",
    "color=c=black:s=160x120:r=10:d=1","-an","-c:v","mpeg4","-q:v","5",video.absolutePath))
   assertTrue("Video fixture failed: ${videoGeneration.allLogsAsString}",ReturnCode.isSuccess(videoGeneration.returnCode))
   val audioGeneration=FFmpegKit.executeWithArguments(arrayOf("-nostdin","-y","-f","lavfi","-i",
    "sine=frequency=1000:duration=1","-vn","-c:a","aac",audio.absolutePath))
   assertTrue("Audio fixture failed: ${audioGeneration.allLogsAsString}",ReturnCode.isSuccess(audioGeneration.returnCode))
   assertTrue(video.length()>0L && audio.length()>0L)
   val result=MediaProcessingEngine(context).mergeFiles(video,audio,merged)
   assertTrue("Mux failed: ${result.exceptionOrNull()?.message}",result.isSuccess)
   assertTrue(merged.isFile && merged.length()>0L)
   val verify=FFmpegKit.executeWithArguments(arrayOf("-nostdin","-v","error","-i",merged.absolutePath,
    "-map","0:v:0","-map","0:a:0","-f","null","-"))
   assertTrue("Merged file failed decoding: ${verify.allLogsAsString}",ReturnCode.isSuccess(verify.returnCode))
  } finally { work.deleteRecursively() }
 }
}
