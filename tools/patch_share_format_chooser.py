#!/usr/bin/env python3
"""Patch the download chooser to separate every extracted video and audio format."""
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "project")
target = root / "app/src/main/java/com/example/ui/components/MtaDialogs.kt"
if not target.is_file():
    raise SystemExit(f"Download dialog source not found: {target}")

source = target.read_text(encoding="utf-8")
if "selectedMediaKind" in source and "audioOptionIndices" in source:
    print("Video/audio format chooser already applied.")
    raise SystemExit(0)

signature = """) {
    AlertDialog(
        onDismissRequest = onDismiss,"""
replacement = """) {
    val audioOptionIndices = pendingRequest.qualities.mapIndexedNotNull { index, quality ->
        val isSubtitle = quality.id.startsWith("newpipe_subtitle_")
        val isAudio = quality.mimeType.startsWith("audio/", ignoreCase = true) ||
            quality.id.startsWith("newpipe_audio_")
        if (isAudio && !isSubtitle) index else null
    }
    val videoOptionIndices = pendingRequest.qualities.mapIndexedNotNull { index, quality ->
        val isSubtitle = quality.id.startsWith("newpipe_subtitle_")
        val isAudio = quality.mimeType.startsWith("audio/", ignoreCase = true) ||
            quality.id.startsWith("newpipe_audio_")
        if (!isAudio && !isSubtitle) index else null
    }
    var selectedMediaKind by remember(pendingRequest) {
        mutableStateOf(if (selectedQualityIndex in audioOptionIndices) "audio" else "video")
    }

    AlertDialog(
        onDismissRequest = onDismiss,"""
if "selectedMediaKind" not in source:
    if signature not in source:
        raise SystemExit("Could not find DownloadOptionsDialog declaration anchor")
    source = source.replace(signature, replacement, 1)

old_outer = """            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {"""
new_outer = """            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 440.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {"""
if new_outer not in source:
    if old_outer not in source:
        raise SystemExit("Could not find download dialog content column")
    source = source.replace(old_outer, new_outer, 1)

start = source.find('                Text(\n                    text = "اختر الجودة والمسار المستخرج:",')
end_marker = """                }
            }
        },
        confirmButton = {"""
end = source.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("Could not locate existing quality list in DownloadOptionsDialog")

new_options = """                Text(
                    text = "1. اختر نوع التنزيل:",
                    style = MaterialTheme.typography.labelLarge,
                    color = MtaTextPrimary
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    listOf(
                        Triple("video", "فيديو", videoOptionIndices.size),
                        Triple("audio", "صوت", audioOptionIndices.size)
                    ).forEach { (kind, label, count) ->
                        val selected = selectedMediaKind == kind
                        Surface(
                            modifier = Modifier
                                .weight(1f)
                                .clickable {
                                    selectedMediaKind = kind
                                    val indices = if (kind == "audio") audioOptionIndices else videoOptionIndices
                                    indices.firstOrNull()?.let(onSelectQuality)
                                }
                                .testTag("download_kind_$kind"),
                            color = if (selected) MtaNeonBlue.copy(alpha = 0.18f) else MtaSurfaceElevated,
                            shape = RoundedCornerShape(12.dp),
                            border = BorderStroke(
                                1.dp,
                                if (selected) MtaNeonBlue else MtaBorderSubtle
                            )
                        ) {
                            Text(
                                text = "$label ($count)",
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 12.dp),
                                color = if (selected) MtaCyanGlow else MtaTextSecondary,
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }

                Text(
                    text = if (selectedMediaKind == "audio") {
                        "2. اختر صيغة الصوت والجودة:"
                    } else {
                        "2. اختر صيغة الفيديو والدقة:"
                    },
                    style = MaterialTheme.typography.labelLarge,
                    color = MtaTextPrimary
                )

                val visibleOptionIndices =
                    if (selectedMediaKind == "audio") audioOptionIndices else videoOptionIndices

                if (visibleOptionIndices.isEmpty()) {
                    Text(
                        text = if (selectedMediaKind == "audio") {
                            "لم يتمكن المحرك من استخراج صيغ صوت مستقلة لهذا الرابط."
                        } else {
                            "لم يتمكن المحرك من استخراج صيغ فيديو لهذا الرابط."
                        },
                        color = MtaTextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(vertical = 12.dp)
                    )
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        visibleOptionIndices.forEach { index ->
                            val quality = pendingRequest.qualities[index]
                            val isSelected = index == selectedQualityIndex
                            Surface(
                                color = if (isSelected) MtaNeonBlue.copy(alpha = 0.15f) else MtaSurfaceElevated,
                                shape = RoundedCornerShape(12.dp),
                                border = BorderStroke(
                                    width = 1.dp,
                                    color = if (isSelected) MtaNeonBlue else MtaBorderSubtle
                                ),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onSelectQuality(index) }
                                    .testTag("quality_option_${quality.id}")
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(horizontal = 10.dp, vertical = 8.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    RadioButton(
                                        selected = isSelected,
                                        onClick = { onSelectQuality(index) },
                                        colors = RadioButtonDefaults.colors(
                                            selectedColor = MtaNeonBlue,
                                            unselectedColor = MtaTextSecondary
                                        )
                                    )
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            text = "${quality.label} • ${quality.format}",
                                            style = MaterialTheme.typography.labelLarge,
                                            color = MtaTextPrimary,
                                            maxLines = 2,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                    }
                                    Text(
                                        text = quality.sizeEstimate,
                                        style = MaterialTheme.typography.labelMedium,
                                        color = MtaCyanGlow
                                    )
                                }
                            }
                        }
                    }
                }
"""
source = source[:start] + new_options + source[end:]
for import_line in (
    "import androidx.compose.foundation.rememberScrollState",
    "import androidx.compose.foundation.verticalScroll",
    "import androidx.compose.foundation.layout.heightIn",
):
    if import_line not in source:
        if import_line.endswith("heightIn"):
            source = source.replace("import androidx.compose.foundation.layout.height\n",
                                    "import androidx.compose.foundation.layout.height\n" + import_line + "\n", 1)
        else:
            source = source.replace("import androidx.compose.foundation.clickable\n",
                                    "import androidx.compose.foundation.clickable\n" + import_line + "\n", 1)

target.write_text(source, encoding="utf-8")
print("Applied separate video/audio format selection with scrollable complete format lists.")
