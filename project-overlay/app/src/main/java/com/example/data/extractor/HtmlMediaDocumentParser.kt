package com.example.data.extractor

import org.jsoup.Jsoup

data class HtmlMediaDocument(
    val title: String?,
    val thumbnailUrl: String?,
    val streamUrls: List<String>
)

/** HTML5-aware metadata parser: handles reordered attributes, entity decoding and relative URLs. */
internal object HtmlMediaDocumentParser {
    fun parse(html: String, pageUrl: String): HtmlMediaDocument {
        val document = Jsoup.parse(html, pageUrl)
        fun meta(name: String): String? = document.select("meta[property], meta[name]")
            .firstOrNull {
                it.attr("property").equals(name, ignoreCase = true) ||
                    it.attr("name").equals(name, ignoreCase = true)
            }
            ?.attr("content")
            ?.trim()
            ?.takeIf { it.isNotEmpty() }

        val title = meta("og:title")
            ?: document.title().replace(Regex("\\s+"), " ").trim().takeIf { it.isNotEmpty() }?.take(160)
        val thumbnail = meta("og:image") ?: meta("twitter:image")
        val streams = document.select("video[src], video source[src], source[src]")
            .mapNotNull { element ->
                element.absUrl("src").takeIf { it.isNotBlank() }
                    ?: element.attr("src").trim().takeIf { it.isNotBlank() }
            }
            .distinct()
            .take(24)
        return HtmlMediaDocument(title, thumbnail, streams)
    }
}
