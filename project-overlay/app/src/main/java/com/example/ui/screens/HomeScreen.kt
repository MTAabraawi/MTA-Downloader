package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.CloudDownload
import androidx.compose.material.icons.filled.ContentPaste
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.R
import com.example.data.local.DownloadEntity
import com.example.data.model.DownloadStatus
import com.example.data.model.SupportedSite
import com.example.data.model.VideoItem
import com.example.ui.components.YouTubeStyleVideoCard
import com.example.ui.theme.*

@Composable
fun HomeScreen(
    videos: List<VideoItem>,
    categories: List<String>,
    selectedCategory: String,
    searchQuery: String,
    supportedSites: List<SupportedSite>,
    activeDownloadsCount: Int,
    recentDownloads: List<DownloadEntity>,
    onSearchQueryChange: (String) -> Unit,
    onAnalyzeUrlClick: (String) -> Unit,
    onCategorySelected: (String) -> Unit,
    onSiteClick: (SupportedSite) -> Unit,
    onWatchVideoClick: (VideoItem) -> Unit,
    onDownloadVideoClick: (VideoItem) -> Unit,
    onOpenDownloadsClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val focusManager = LocalFocusManager.current
    val clipboard = LocalClipboardManager.current

    LazyColumn(
        modifier = modifier.fillMaxSize().background(MtaDarkNavy),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp)
    ) {
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(11.dp)) {
                    androidx.compose.foundation.Image(
                        painter = painterResource(R.drawable.mta_launcher_icon),
                        contentDescription = "MTA Downloader",
                        modifier = Modifier.size(46.dp).clip(RoundedCornerShape(14.dp))
                    )
                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(stringResource(R.string.app_name), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = MtaTextPrimary)
                        Text("حمّل ما تريد، من مكان واحد", style = MaterialTheme.typography.labelSmall, color = MtaTextSecondary)
                    }
                }
                Surface(
                    modifier = Modifier.clickable(onClick = onOpenDownloadsClick).testTag("header_downloads_badge"),
                    color = MtaSurfaceElevated, shape = RoundedCornerShape(14.dp),
                    border = BorderStroke(1.dp, if (activeDownloadsCount > 0) MtaNeonBlue else MtaBorderSubtle)
                ) {
                    Row(Modifier.padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                        Icon(Icons.Filled.CloudDownload, contentDescription = stringResource(R.string.nav_downloads), tint = MtaCyanGlow, modifier = Modifier.size(18.dp))
                        Text(if (activeDownloadsCount > 0) "$activeDownloadsCount نشط" else "تنزيلاتي", color = MtaTextPrimary, style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
        }

        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("ما الذي تريد تنزيله اليوم؟", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = MtaTextPrimary)
                Text("ألصق رابط الفيديو أو الصوت، وسنبحث عن أفضل صيغة متاحة.", style = MaterialTheme.typography.bodyMedium, color = MtaTextSecondary)
                OutlinedTextField(
                    value = searchQuery, onValueChange = onSearchQueryChange,
                    modifier = Modifier.fillMaxWidth().testTag("home_search_input"),
                    placeholder = { Text(stringResource(R.string.search_or_paste_hint), maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null, tint = MtaCyanGlow) },
                    trailingIcon = {
                        if (searchQuery.isNotEmpty()) {
                            IconButton(onClick = { onSearchQueryChange("") }) { Icon(Icons.Filled.Clear, contentDescription = "مسح", tint = MtaTextSecondary) }
                        } else {
                            IconButton(onClick = { clipboard.getText()?.text?.let(onSearchQueryChange) }) {
                                Icon(Icons.Filled.ContentPaste, contentDescription = "لصق الرابط", tint = MtaCyanGlow)
                            }
                        }
                    },
                    singleLine = true, shape = RoundedCornerShape(17.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = MtaSurfaceNavy, unfocusedContainerColor = MtaSurfaceNavy,
                        focusedBorderColor = MtaNeonBlue, unfocusedBorderColor = MtaBorderSubtle,
                        focusedTextColor = MtaTextPrimary, unfocusedTextColor = MtaTextPrimary, cursorColor = MtaCyanGlow
                    ),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Go),
                    keyboardActions = KeyboardActions(onGo = {
                        focusManager.clearFocus()
                        if (searchQuery.isNotBlank()) onAnalyzeUrlClick(searchQuery)
                    })
                )
                Button(
                    onClick = { focusManager.clearFocus(); onAnalyzeUrlClick(searchQuery) },
                    modifier = Modifier.fillMaxWidth().height(52.dp).testTag("analyze_url_button"),
                    shape = RoundedCornerShape(15.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MtaNeonBlue, contentColor = Color.White)
                ) {
                    Icon(Icons.Filled.Link, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.btn_analyze_url), fontWeight = FontWeight.Bold)
                }
            }
        }

        item {
            Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(22.dp), color = MtaSurfaceNavy, border = BorderStroke(1.dp, MtaNeonBlue.copy(alpha = 0.45f))) {
                Box(Modifier.background(Brush.horizontalGradient(listOf(Color(0xFF123B68), MtaSurfaceNavy, MtaDarkNavy))).padding(18.dp)) {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                            Icon(Icons.Filled.Bolt, contentDescription = null, tint = MtaCyanGlow, modifier = Modifier.size(18.dp))
                            Text("محركات تنزيل متعددة", color = MtaCyanGlow, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
                        }
                        Text("من الرابط إلى الملف", color = Color.White, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                        Text("تحليل الرابط، اختيار الجودة والصيغة، ثم متابعة التنزيل من شاشة واحدة.", color = Color.White.copy(alpha = 0.82f), style = MaterialTheme.typography.bodyMedium)
                        Row(horizontalArrangement = Arrangement.spacedBy(7.dp), verticalAlignment = Alignment.CenterVertically) {
                            FeaturePill("اختيار الجودة")
                            FeaturePill("متابعة التقدم")
                            FeaturePill("بلا إعلانات")
                        }
                    }
                }
            }
        }

        item {
            Column(verticalArrangement = Arrangement.spacedBy(11.dp)) {
                SectionHeading("تصفح المنصات", "افتح المنصة داخل المتصفح الذكي")
                LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(vertical = 2.dp)) {
                    items(supportedSites, key = { it.id }) { site ->
                        Column(
                            modifier = Modifier.width(76.dp).clip(RoundedCornerShape(16.dp)).clickable { onSiteClick(site) }
                                .padding(vertical = 7.dp).testTag("site_shortcut_\${site.id}"),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(7.dp)
                        ) {
                            Box(Modifier.size(54.dp).clip(CircleShape).background(MtaSurfaceElevated), contentAlignment = Alignment.Center) {
                                Text(site.name.take(1).uppercase(), color = Color(site.badgeColorHex), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                            }
                            Text(site.name.substringBefore(" "), color = MtaTextPrimary, style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
            }
        }

        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                SectionHeading("استكشف حسب النوع", "اختر تصنيفاً لتصفية المحتوى المتاح")
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(categories, key = { it }) { category ->
                        FilterChip(
                            selected = selectedCategory == category, onClick = { onCategorySelected(category) },
                            label = { Text(category) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = MtaNeonBlue.copy(alpha = 0.22f),
                                selectedLabelColor = MtaCyanGlow, labelColor = MtaTextSecondary
                            )
                        )
                    }
                }
            }
        }

        if (recentDownloads.isNotEmpty()) {
            item {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    SectionHeading("آخر التنزيلات", "تابع ملفاتك الأخيرة")
                    TextButton(onClick = onOpenDownloadsClick) { Text("عرض الكل", color = MtaCyanGlow) }
                }
            }
            items(recentDownloads.take(4), key = { "recent_\${it.id}" }) { download ->
                RecentDownloadCard(download = download, onClick = onOpenDownloadsClick)
            }
        }

        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                SectionHeading("محتوى تم تحليله", "تظهر هنا الروابط التي تم تحليلها فعلياً")
                Icon(Icons.Filled.PlayArrow, contentDescription = null, tint = MtaCyanGlow)
            }
        }

        if (videos.isEmpty()) {
            item {
                Surface(Modifier.fillMaxWidth(), color = MtaSurfaceNavy, shape = RoundedCornerShape(18.dp), border = BorderStroke(1.dp, MtaBorderSubtle)) {
                    Column(Modifier.padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(9.dp)) {
                        Icon(Icons.Filled.Language, contentDescription = null, tint = MtaNeonBlue, modifier = Modifier.size(34.dp))
                        Text("لا توجد نتائج بعد", color = MtaTextPrimary, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text("ابدأ بلصق رابط عام في الأعلى أو اختر منصة للتصفح. لن نعرض مقاطع تجريبية أو روابط غير حقيقية.", color = MtaTextSecondary, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        } else {
            items(videos, key = { it.id }) { video ->
                YouTubeStyleVideoCard(video = video, onWatchClick = onWatchVideoClick, onDownloadClick = onDownloadVideoClick)
            }
        }
    }
}

@Composable
private fun SectionHeading(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(title, color = MtaTextPrimary, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(subtitle, color = MtaTextSecondary, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun FeaturePill(text: String) {
    Surface(color = Color.White.copy(alpha = 0.09f), shape = RoundedCornerShape(50)) {
        Text(text, modifier = Modifier.padding(horizontal = 9.dp, vertical = 6.dp), color = Color.White, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun RecentDownloadCard(download: DownloadEntity, onClick: () -> Unit) {
    val status = runCatching { DownloadStatus.valueOf(download.status) }.getOrDefault(DownloadStatus.FAILED)
    val statusLabel = when (status) {
        DownloadStatus.QUEUED -> "في قائمة الانتظار"
        DownloadStatus.DOWNLOADING -> "جارٍ التنزيل"
        DownloadStatus.PAUSED -> "متوقف مؤقتاً"
        DownloadStatus.COMPLETED -> "اكتمل"
        DownloadStatus.FAILED -> "تعذر التنزيل"
    }
    Surface(Modifier.fillMaxWidth().clickable(onClick = onClick), color = MtaSurfaceNavy, shape = RoundedCornerShape(16.dp), border = BorderStroke(1.dp, MtaBorderSubtle)) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Box(Modifier.size(42.dp).clip(RoundedCornerShape(12.dp)).background(MtaSurfaceElevated), contentAlignment = Alignment.Center) {
                    Icon(if (status == DownloadStatus.COMPLETED) Icons.Filled.CheckCircle else Icons.Filled.Download, contentDescription = null, tint = if (status == DownloadStatus.COMPLETED) Color(0xFF35D39A) else MtaCyanGlow)
                }
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(download.title, color = MtaTextPrimary, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text("\${download.sourcePlatform} • $statusLabel", color = MtaTextSecondary, style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Text("\${download.progress.coerceIn(0, 100)}%", color = MtaCyanGlow, style = MaterialTheme.typography.labelMedium)
            }
            if (status == DownloadStatus.DOWNLOADING || status == DownloadStatus.QUEUED) {
                LinearProgressIndicator(
                    progress = { download.progress.coerceIn(0, 100) / 100f },
                    modifier = Modifier.fillMaxWidth().height(4.dp).clip(CircleShape),
                    color = MtaNeonBlue, trackColor = MtaSurfaceElevated
                )
            }
        }
    }
}
