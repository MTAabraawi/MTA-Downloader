package com.example.data.extractor

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.HeaderMap
import retrofit2.http.Url

/**
 * Dynamic-URL page fetcher. The host is validated by MediaExtractorEngine before this API is called.
 * OkHttp remains the shared transport so timeouts, redirect policy and connection pooling stay consistent.
 */
internal interface PublicPageApi {
    @GET
    suspend fun fetchPage(
        @Url url: String,
        @HeaderMap headers: Map<String, String>
    ): Response<ResponseBody>
}
