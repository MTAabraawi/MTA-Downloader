#!/usr/bin/env python3
"""Inspect the yt-dlp Android AAR for embedded Python package metadata and source files."""
import argparse
import io
import json
import re
import zipfile
from email.parser import Parser
from pathlib import Path

def scan_archive(archive, archive_label, packages, relevant_entries, version_hints, depth=0, archives_scanned=None):
    if archives_scanned is not None:
        archives_scanned.append(archive_label)
    for name in archive.namelist():
        lower = name.lower()
        full_name = archive_label + "!/" + name
        if any(token in lower for token in ("yt_dlp", "yt-dlp", "certifi", "chaquopy", "python", "ffmpeg", "third-party-notices")):
            if len(relevant_entries) < 500:
                relevant_entries.append(full_name)
        if lower.endswith(".dist-info/metadata"):
            metadata = Parser().parsestr(archive.read(name).decode("utf-8", errors="replace"))
            license_value = metadata.get("License-Expression") or metadata.get("License") or "NOT_REPORTED"
            classifiers = [item for item in metadata.get_all("Classifier", []) if item.startswith("License ::")]
            if license_value == "NOT_REPORTED" and classifiers:
                license_value = "; ".join(classifiers)
            packages.append({
                "name": metadata.get("Name", name.split("/")[-2].removesuffix(".dist-info")),
                "version": metadata.get("Version", "unknown"),
                "license": license_value,
                "metadata_path": full_name,
                "aar": archive_label,
            })
        if lower.endswith("/yt_dlp/version.py") or lower.endswith("/yt_dlp/version.pyc"):
            if lower.endswith(".py"):
                source = archive.read(name).decode("utf-8", errors="replace")
                match = re.search(r"""(?m)^__version__\s*=\s*(['"])([^'"]+)\1""", source)
                if match:
                    version_hints["yt-dlp"] = match.group(2)
        if lower.endswith("/certifi/__init__.py"):
            source = archive.read(name).decode("utf-8", errors="replace")
            match = re.search(r"""(?m)^__version__\s*=\s*(['"])([^'"]+)\1""", source)
            if match:
                version_hints["certifi"] = match.group(2)
        if lower.endswith("chaquopy_java-17.0.0.jar"):
            version_hints["chaquopy-java"] = "17.0.0"
        python_version = re.search(r"libpython3\.(\d+)\.so$", lower)
        if python_version:
            version_hints["cpython"] = "3." + python_version.group(1)
        # Chaquopy .imy files are ZIP archives, just like wheels. The prior scanner
        # ignored them, which silently reported zero Python packages despite the AAR
        # carrying certifi and the embedded yt-dlp runtime.
        if lower.endswith((".zip", ".whl", ".imy", ".jar")) and depth < 4:
            try:
                nested = zipfile.ZipFile(io.BytesIO(archive.read(name)))
                scan_archive(
                    nested, full_name, packages, relevant_entries, version_hints,
                    depth + 1, archives_scanned
                )
            except (OSError, zipfile.BadZipFile, KeyError):
                pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gradle-cache", type=Path, default=Path.home() / ".gradle/caches")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    aar_files = list(args.gradle_cache.glob(
        "modules-2/files-2.1/dev.ffmpegkit-maintained/yt-dlp-android/2.0.2/**/*.aar"
    ))
    packages, relevant_entries, version_hints = [], [], {}
    inspected = []
    archives_scanned = []
    for aar in aar_files:
        inspected.append(str(aar))
        with zipfile.ZipFile(aar) as archive:
            scan_archive(archive, aar.name, packages, relevant_entries, version_hints, archives_scanned=archives_scanned)
    result = {
        "wrapper": "dev.ffmpegkit-maintained:yt-dlp-android:2.0.2",
        "aar_files_inspected": inspected,
        "python_distributions": sorted(packages, key=lambda item: item["name"].lower()),
        "version_hints_from_sources": version_hints,
        "relevant_archive_entries": relevant_entries,
        "nested_archives_scanned": archives_scanned,
        "metadata_found": bool(packages),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Inspected " + str(len(aar_files)) + " AAR(s); scanned " + str(len(archives_scanned)) +
          " nested ZIP/WHL/IMY/JAR archives; found " + str(len(packages)) +
          " Python distribution metadata record(s), version hints=" + str(version_hints) +
          ", relevant archive entries=" + str(len(relevant_entries)))
    if not packages:
        raise SystemExit("No Python distribution metadata found after scanning Chaquopy .imy archives; license audit is incomplete.")

if __name__ == "__main__":
    main()
