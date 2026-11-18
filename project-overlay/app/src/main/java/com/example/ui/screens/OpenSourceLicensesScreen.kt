package com.example.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp

@Composable
fun OpenSourceLicensesScreen() {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val licenseBundle = remember {
        runCatching {
            context.assets.open("open-source-licenses/OPEN_SOURCE_LICENSES.txt")
                .bufferedReader().use { it.readText() }
        }.getOrElse { "تعذر تحميل ملف نصوص التراخيص من أصول التطبيق." }
    }
    val wrapperNotices = remember {
        runCatching {
            context.assets.open("THIRD-PARTY-NOTICES.txt")
                .bufferedReader().use { it.readText() }
        }.getOrElse { "لم يتم العثور على إشعارات الغلاف داخل الأصول المدمجة." }
    }
    var selectedDocument by remember { mutableStateOf<String?>(null) }
    var selectedTitle by remember { mutableStateOf("") }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("التراخيص مفتوحة المصدر", style = MaterialTheme.typography.headlineSmall)
        Text(
            "يعتمد MTA Downloader على مكتبات ومكونات مفتوحة المصدر. تعرض هذه الصفحة أسماء المكونات وتراخيصها وروابط مصادرها ونصوص التراخيص المرفقة."
        )
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("MTA Downloader", style = MaterialTheme.typography.titleMedium)
                Text("GNU GPL v3-or-later — كود التطبيق ومصادر التعديلات")
                Text("المصدر: github.com/MTAabraawi/MTA-Downloader")
            }
        }
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("NewPipe Extractor 0.27.1", style = MaterialTheme.typography.titleMedium)
                Text("GPL-3.0-or-later — محرك استخراج مدمج")
                Text("المصدر: github.com/TeamNewPipe/NewPipeExtractor")
            }
        }
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("yt-dlp", style = MaterialTheme.typography.titleMedium)
                Text("Unlicense — محرك استخراج يعمل داخل الغلاف Android")
                Text("المصدر: github.com/yt-dlp/yt-dlp")
            }
        }
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("yt-dlp-android 2.0.2", style = MaterialTheme.typography.titleMedium)
                Text("MIT — غلاف Android، ويضم Python 3.13 وChaquopy وCertifi")
                Text("المصدر: github.com/ffmpegkit-maintained/yt-dlp-android")
            }
        }
        Text(
            "الإشعارات القانونية: يقدّم البرنامج دون ضمان بالقدر الذي يسمح به القانون. يجوز إعادة توزيع المكونات المغطاة برخصها مع الالتزام بشروطها. نصوص التراخيص ومعلومات المصدر متاحة أدناه."
        )
        Button(onClick = {
            selectedTitle = "نصوص التراخيص المفتوحة"
            selectedDocument = licenseBundle
        }) {
            Text("عرض نصوص التراخيص الكاملة")
        }
        OutlinedButton(onClick = {
            selectedTitle = "إشعارات yt-dlp-android"
            selectedDocument = wrapperNotices
        }) {
            Text("عرض إشعارات المكونات المضمنة")
        }
        OutlinedButton(onClick = {
            uriHandler.openUri("https://github.com/MTAabraawi/MTA-Downloader")
        }) {
            Text("فتح مصدر التطبيق")
        }
    }

    selectedDocument?.let { document ->
        AlertDialog(
            onDismissRequest = { selectedDocument = null },
            title = { Text(selectedTitle) },
            text = {
                Box(Modifier.heightIn(max = 480.dp).verticalScroll(rememberScrollState())) {
                    Text(document, style = MaterialTheme.typography.bodySmall)
                }
            },
            confirmButton = {
                TextButton(onClick = { selectedDocument = null }) { Text("إغلاق") }
            }
        )
    }
}
