#!/usr/bin/env python3
"""Create a transparent dependency/license and FFmpeg packaging audit from a CycloneDX SBOM."""
import argparse
import json
import re
import zipfile
from pathlib import Path
from email.parser import Parser

def license_names(component):
    found = []
    for item in component.get("licenses", []) or []:
        lic = item.get("license") or item.get("expression") or {}
        if isinstance(lic, dict):
            found.append(lic.get("id") or lic.get("name") or "UNKNOWN")
        elif isinstance(lic, str):
            found.append(lic)
    return sorted(set(found)) or ["NOT_REPORTED"]

def archive_names(path):
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bom", required=True, type=Path)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--gradle-cache", type=Path, default=Path.home() / ".gradle/caches")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    bom = json.loads(args.bom.read_text(encoding="utf-8"))
    components = sorted(bom.get("components", []), key=lambda c: (c.get("name", "").lower(), c.get("version", "")))
    missing = [c for c in components if license_names(c) == ["NOT_REPORTED"]]

    apk_entries = archive_names(args.apk)
    required_license_assets = [
        "open-source-licenses/OPEN_SOURCE_LICENSES.txt",
        "open-source-licenses/DEPENDENCY_SBOM.json",
        "open-source-licenses/EMBEDDED_PYTHON_PACKAGES.json",
        "THIRD-PARTY-NOTICES.txt",
    ]
    missing_license_assets = [
        asset for asset in required_license_assets
        if not any(entry.endswith(asset) for entry in apk_entries)
    ]
    if missing_license_assets:
        raise SystemExit("Required in-app license asset(s) missing from APK: " + ", ".join(missing_license_assets))

    aar_candidates = list(args.gradle_cache.glob(
        "modules-2/files-2.1/dev.ffmpegkit-maintained/yt-dlp-android/2.0.2/**/*.aar"
    ))
    aar_entries = []
    python_packages = []
    for aar in aar_candidates:
        try:
            with zipfile.ZipFile(aar) as archive:
                names = archive.namelist()
                aar_entries.extend((aar.name + "!/" + name) for name in names)
                for metadata_path in (name for name in names if name.endswith(".dist-info/METADATA")):
                    metadata = Parser().parsestr(archive.read(metadata_path).decode("utf-8", errors="replace"))
                    package_license = metadata.get("License-Expression") or metadata.get("License") or "NOT_REPORTED"
                    classifiers = [value for value in metadata.get_all("Classifier", []) if value.startswith("License ::")]
                    if package_license == "NOT_REPORTED" and classifiers:
                        package_license = "; ".join(classifiers)
                    python_packages.append({
                        "name": metadata.get("Name", metadata_path.split("/")[-2].removesuffix(".dist-info")),
                        "version": metadata.get("Version", "unknown"),
                        "license": package_license,
                        "metadata": metadata_path,
                    })
        except (OSError, zipfile.BadZipFile):
            continue

    ffmpeg_pattern = re.compile(r"(?:^|[/!])(?:lib)?(?:avcodec|avformat|avutil|avfilter|avdevice|postproc|swresample|swscale|ffmpeg)(?:[._-]|$)|ffmpegkit", re.I)
    apk_ffmpeg = [name for name in apk_entries if ffmpeg_pattern.search(name)]
    aar_ffmpeg = [name for name in aar_entries if ffmpeg_pattern.search(name)]
    ffmpeg_components = [c for c in components if "ffmpeg" in c.get("name", "").lower() or "ffmpegkit" in c.get("name", "").lower()]

    lines = [
        "# MTA Downloader — dependency and license audit",
        "",
        "- CycloneDX spec: " + str(bom.get("specVersion", "unknown")),
        "- Components in aggregate SBOM: " + str(len(components)),
        "- Components with no license metadata: " + str(len(missing)),
        "- APK inspected: " + args.apk.name,
        "- yt-dlp Android AAR candidates found in Gradle cache: " + str(len(aar_candidates)),
        "- Required in-app license assets present: " + str(len(required_license_assets) - len(missing_license_assets)) + "/" + str(len(required_license_assets)),
        "- Python distributions discovered inside those AARs: " + str(len(python_packages)),
        "",
        "## FFmpeg packaging inspection",
        "",
    ]
    if apk_ffmpeg or aar_ffmpeg or ffmpeg_components:
        lines.append("**Potential FFmpeg components were detected. Manual license/build-configuration review is required before release.**")
        for item in sorted(set(apk_ffmpeg + aar_ffmpeg)):
            lines.append("- Binary/archive entry: " + item)
        for item in ffmpeg_components:
            lines.append("- SBOM component: " + item.get("name", "unknown") + ":" + item.get("version", "unknown"))
    else:
        lines += [
            "No FFmpeg/FFmpegKit component name or FFmpeg native-library filename was found in the resolved SBOM, APK entry list, or inspected yt-dlp Android AAR entries.",
            "",
            "This is a package-content finding, not proof that runtime code can never invoke an externally supplied FFmpeg executable. The inspected yt-dlp Android wrapper documents an embedded CPython/yt-dlp/Certifi runtime; it does not document bundling FFmpeg.",
        ]

    lines += ["", "## Python distributions discovered inside the yt-dlp Android AAR", "", "| Package | Version | License metadata |", "|---|---:|---|"]
    if python_packages:
        for package in sorted(python_packages, key=lambda p: p["name"].lower()):
            lines.append("| " + package["name"] + " | " + package["version"] + " | " + package["license"].replace("|", "\\|") + " |")
    else:
        lines.append("No .dist-info/METADATA records were found in the cached AAR; inspect the AAR contents and upstream packaging manually.")

    lines += ["", "## Components and declared licenses", "", "| Component | Version | License metadata |", "|---|---:|---|"]
    for component in components:
        name = component.get("name", "unknown").replace("|", "\\|")
        version = component.get("version", "unspecified").replace("|", "\\|")
        licenses = ", ".join(license_names(component)).replace("|", "\\|")
        lines.append("| " + name + " | " + version + " | " + licenses + " |")

    lines += ["", "## Components requiring manual license metadata review", ""]
    if missing:
        for component in missing:
            lines.append("- " + component.get("name", "unknown") + ":" + component.get("version", "unspecified"))
    else:
        lines.append("None reported by the generated SBOM.")

    lines += [
        "",
        "## Manually identified bundled runtime components",
        "",
        "| Component | Version/source | License | Evidence/status |",
        "|---|---|---|---|",
        "| NewPipe Extractor | 0.27.1 | GPL-3.0-or-later | Upstream project license; source/notice must accompany distribution |",
        "| yt-dlp | Version embedded in AAR; resolve from packaged Python metadata during release audit | Unlicense | Wrapper third-party notice; version still needs extraction from AAR |",
        "| yt-dlp-android | 2.0.2 | MIT | Upstream repository LICENSE |",
        "| Chaquopy | Bundled by wrapper | MIT | Wrapper THIRD-PARTY-NOTICES; exact bundled distribution details to verify |",
        "| CPython | 3.13 | PSF-2.0 | Wrapper README architecture; include PSF license text |",
        "| Certifi | Version embedded in AAR | MPL-2.0 | Wrapper declares pip install certifi; extract exact version and package license from AAR before release |",
        "",
        "## Release blockers",
        "",
        "- This report is a CI-generated inventory, not legal advice or a completed legal opinion.",
        "- Resolve every NOT_REPORTED license and inspect native libraries embedded inside AARs, not just Gradle module names.",
        "- Extract exact yt-dlp, Certifi, CPython, and Chaquopy versions from the AAR/package metadata and archive their corresponding source/notice materials. The AAR metadata scan above lists Python distributions where wheel metadata is present.",
        "- NewPipe Extractor is GPL-3.0-or-later. Prepare and publish the corresponding source and build/patch scripts for the shipped binary, and verify the complete app distribution obligations before release.",
        "- Do not claim FFmpeg is shipped unless the final APK/AAR inspection identifies it. If later added, record its exact build flags, enabled codecs/libraries, license mode (LGPL/GPL/nonfree), source revision, modifications, and corresponding source.",
        "- Keep the generated SBOM and this audit report with each release artifact.",
        "",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    manifest = args.output.with_name("embedded-python-packages.json")
    manifest.write_text(json.dumps({
        "wrapper": "dev.ffmpegkit-maintained:yt-dlp-android:2.0.2",
        "aar_files_inspected": [str(path) for path in aar_candidates],
        "python_distributions": python_packages,
        "metadata_found": bool(python_packages),
    }, indent=2), encoding="utf-8")
    print("Wrote " + str(args.output) + "; components=" + str(len(components)) + ", missing_license_metadata=" + str(len(missing)) + ", ffmpeg_apk=" + str(len(apk_ffmpeg)) + ", ffmpeg_aar=" + str(len(aar_ffmpeg)))

if __name__ == "__main__":
    main()
