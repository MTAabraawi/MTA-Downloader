#!/usr/bin/env python3
"""Inspect the yt-dlp Android AAR for embedded Python package metadata."""
import argparse
import json
import zipfile
from email.parser import Parser
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gradle-cache", type=Path, default=Path.home() / ".gradle/caches")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    aar_files = list(args.gradle_cache.glob(
        "modules-2/files-2.1/dev.ffmpegkit-maintained/yt-dlp-android/2.0.2/**/*.aar"
    ))
    packages = []
    inspected = []
    for aar in aar_files:
        inspected.append(str(aar))
        with zipfile.ZipFile(aar) as archive:
            for name in archive.namelist():
                if not name.endswith(".dist-info/METADATA"):
                    continue
                metadata = Parser().parsestr(archive.read(name).decode("utf-8", errors="replace"))
                license_value = metadata.get("License-Expression") or metadata.get("License") or "NOT_REPORTED"
                classifiers = [item for item in metadata.get_all("Classifier", []) if item.startswith("License ::")]
                if license_value == "NOT_REPORTED" and classifiers:
                    license_value = "; ".join(classifiers)
                packages.append({
                    "name": metadata.get("Name", name.split("/")[-2].removesuffix(".dist-info")),
                    "version": metadata.get("Version", "unknown"),
                    "license": license_value,
                    "metadata_path": name,
                    "aar": aar.name,
                })
    result = {
        "wrapper": "dev.ffmpegkit-maintained:yt-dlp-android:2.0.2",
        "aar_files_inspected": inspected,
        "python_distributions": sorted(packages, key=lambda item: item["name"].lower()),
        "metadata_found": bool(packages),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Inspected " + str(len(aar_files)) + " AAR(s); found " + str(len(packages)) + " Python distribution metadata record(s).")

if __name__ == "__main__":
    main()
