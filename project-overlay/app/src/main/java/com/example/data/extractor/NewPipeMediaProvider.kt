package com.example.data.extractor

import okhttp3.OkHttpClient
import okhttp3.RequestBody.Companion.toRequestBody
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.StreamingService
import org.schabi.newpipe.extractor.downloader.Downloader
import org.schabi.newpipe.extractor.downloader.Request as NewPipeRequest
import org.schabi.newpipe.extractor.downloader.Response as NewPipeResponse
import org.schabi.newpipe.extractor.exceptions.ReCaptchaException
import org.schabi.newpipe.extractor.localization.ContentCountry
import org.schabi.newpipe.extractor.localization.Localization
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Small OkHttp adapter required by NewPipe Extractor.
 * It deliberately uses ordinary HTTP requests and does not impersonate browser TLS fingerprints.
 */
internal class OkHttpNewPipeDownloader(
    private val client: OkHttpClient
) : Downloader() {
    @Throws(IOException::class, ReCaptchaException::class)
    override fun execute(request: NewPipeRequest): NewPipeResponse {
        val builder = okhttp3.Request.Builder().url(request.url())
        request.headers().forEach { (name, values) ->
            values.forEach { value -> builder.addHeader(name, value) }
        }
        val method = request.httpMethod().uppercase()
        val bytes = request.dataToSend()
        val body = bytes?.toRequestBody(null)
        val safeBody = when (method) {
            "GET", "HEAD" -> null
            "POST", "PUT", "PATCH" -> body ?: ByteArray(0).toRequestBody(null)
            else -> body
        }
        builder.method(method, safeBody)

        client.newCall(builder.build()).execute().use { response ->
            val responseBody = response.body?.string().orEmpty()
            return NewPipeResponse(
                response.code,
                response.message,
                response.headers.toMultimap(),
                responseBody,
                response.request.url.toString()
            )
        }
    }
}

/**
 * NewPipe supports only the services shipped by its ServiceList. Unsupported URLs return null
 * so the caller can continue to the existing HTML/yt-dlp fallback chain.
 */
internal object NewPipeMediaProvider {
    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .followRedirects(true)
            .followSslRedirects(true)
            .connectTimeout(18, TimeUnit.SECONDS)
            .readTimeout(25, TimeUnit.SECONDS)
            .callTimeout(90, TimeUnit.SECONDS)
            .build()
    }

    @Volatile private var initialized = false

    private fun ensureInitialized() {
        if (initialized) return
        synchronized(this) {
            if (!initialized) {
                NewPipe.init(OkHttpNewPipeDownloader(client), Localization.DEFAULT, ContentCountry.DEFAULT)
                initialized = true
            }
        }
    }

    fun extract(url: String, customTitle: String?, fallbackPlatform: String): com.example.data.model.VideoItem? {
        return runCatching {
            ensureInitialized()
            val service = NewPipe.getServiceByUrl(url)
            if (service.getLinkTypeByUrl(url) != StreamingService.LinkType.STREAM) return null

            val extractor = service.getStreamExtractor(url)
            extractor.fetchPage()

            val formats = buildList {
                extractor.videoStreams
                    .filterNot { it.isVideoOnly }
                    .forEach { stream ->
                        val mediaUrl = stream.content
                        if (mediaUrl.startsWith("https://", true)) {
                            val format = stream.format ?: return@forEach
                            add(
                                com.example.data.model.QualityOption(
                                    id = "newpipe_video_${stream.resolution.lowercase().replace(Regex("[^a-z0-9]+"), "_")}_${format.suffix}",
                                    label = stream.resolution,
                                    format = "${format.name} • ${stream.fps} FPS",
                                    sizeEstimate = "الحجم غير متاح من المصدر",
                                    extension = format.suffix,
                                    mimeType = format.mimeType,
                                    overrideStreamUrl = mediaUrl
                                )
                            )
                        }
                    }
                extractor.audioStreams.forEach { stream ->
                    val mediaUrl = stream.content
                    if (mediaUrl.startsWith("https://", true)) {
                        val format = stream.format ?: return@forEach
                        add(
                            com.example.data.model.QualityOption(
                                id = "newpipe_audio_${format.suffix}_${stream.averageBitrate}",
                                label = "صوت • ${stream.averageBitrate} kbit/s",
                                format = format.name,
                                sizeEstimate = "الحجم غير متاح من المصدر",
                                extension = format.suffix,
                                mimeType = format.mimeType,
                                overrideStreamUrl = mediaUrl
                            )
                        )
                    }
                }

                extractor.subtitlesDefault.forEach { stream ->
                    val subtitleUrl = stream.content
                    val format = stream.format ?: return@forEach
                    if (subtitleUrl.startsWith("https://", true)) {
                        val language = stream.displayLanguageName.ifBlank { stream.languageTag }
                        val generated = if (stream.isAutoGenerated) " • تلقائية" else ""
                        add(
                            com.example.data.model.QualityOption(
                                id = "newpipe_subtitle_${stream.languageTag}_${format.suffix}",
                                label = "ترجمة • ${language}${generated}",
                                format = format.name,
                                sizeEstimate = "حجم غير متاح",
                                extension = format.suffix,
                                mimeType = format.mimeType,
                                overrideStreamUrl = subtitleUrl
                            )
                        )
                    }
                }
            }.distinctBy { it.id }

            if (formats.isEmpty()) return null
            val title = customTitle?.takeIf { it.isNotBlank() } ?: extractor.name
            val uploader = extractor.uploaderName.takeIf { it.isNotBlank() } ?: service.serviceInfo.name
            val firstStream = formats.firstOrNull { !it.id.startsWith("newpipe_subtitle_") }?.overrideStreamUrl ?: return null
            val thumbnailUrl = runCatching { extractor.thumbnails.firstOrNull()?.url }.getOrNull()
            com.example.data.model.VideoItem(
                id = "newpipe_${url.hashCode()}",
                title = title,
                channelName = uploader,
                channelInitial = uploader.firstOrNull()?.uppercase() ?: "M",
                views = extractor.viewCount.takeIf { it >= 0 }?.toString() ?: "غير متاح",
                publishedAgo = "غير متاح",
                duration = extractor.length.toString(),
                category = "محتوى مستخرج",
                sourcePlatform = service.serviceInfo.name.ifBlank { fallbackPlatform },
                thumbnailRes = com.example.R.drawable.img_hero_banner,
                thumbnailUrl = thumbnailUrl,
                streamUrl = firstStream,
                description = "تم استخراج البيانات والصيغ بواسطة NewPipe Extractor. قد تنتهي صلاحية روابط الوسائط المؤقتة.",
                qualities = formats
            )
        }.getOrNull()
    }
}
