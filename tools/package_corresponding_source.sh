#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${1:-${REPO_ROOT}/MTA-DOWNLOADER-CORRESPONDING-SOURCE.zip}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

BUNDLE="$WORK/MTA-DOWNLOADER-CORRESPONDING-SOURCE"
mkdir -p "$BUNDLE/mta-project-inputs" "$BUNDLE/upstream/NewPipeExtractor" "$BUNDLE/upstream/FFmpeg"

cp "$REPO_ROOT/mta-downloader-nov-17-2026-10-15-48-pm.zip" "$BUNDLE/mta-project-inputs/"
cp -a "$REPO_ROOT/project-overlay" "$BUNDLE/mta-project-inputs/"
cp -a "$REPO_ROOT/tools" "$BUNDLE/mta-project-inputs/"
cp -a "$REPO_ROOT/docs" "$BUNDLE/mta-project-inputs/"
cp "$REPO_ROOT/LICENSE" "$BUNDLE/"
cp "$REPO_ROOT/THIRD-PARTY-NOTICES.md" "$BUNDLE/"

git clone --depth 1 --branch v0.27.1 https://github.com/TeamNewPipe/NewPipeExtractor.git "$BUNDLE/upstream/NewPipeExtractor"
git clone --depth 1 --branch v8.1.9-lts-android https://github.com/ffmpegkit-maintained/ffmpeg.git "$BUNDLE/upstream/FFmpeg"
PYTHON_MANIFEST="$REPO_ROOT/project/build/reports/embedded-python-packages.json"
if [[ -f "$PYTHON_MANIFEST" ]]; then
  python3 "$REPO_ROOT/tools/package_python_sources.py" --manifest "$PYTHON_MANIFEST" --output "$BUNDLE/upstream/python-sources"
else
  echo "WARNING: embedded Python package manifest unavailable; inspect the audit report before release."
fi
printf "NewPipe Extractor v0.27.1 commit: %s\n" "$(git -C "$BUNDLE/upstream/NewPipeExtractor" rev-parse HEAD)" > "$BUNDLE/UPSTREAM-VERSIONS.txt"
printf "FFmpegKit Full 8.1.9 tag: v8.1.9-lts-android\nFFmpeg source commit: %s\n" "$(git -C "$BUNDLE/upstream/FFmpeg" rev-parse HEAD)" >> "$BUNDLE/UPSTREAM-VERSIONS.txt"
rm -rf "$BUNDLE/upstream/NewPipeExtractor/.git" "$BUNDLE/upstream/FFmpeg/.git"

cat > "$BUNDLE/BUILDING.md" <<'EOF'
# MTA Downloader corresponding source package

This source package accompanies the GPL-3.0-or-later MTA Downloader build that uses NewPipe Extractor v0.27.1.

## Included material
- The exact original Android project source archive used by the CI validation workflow.
- The reviewed project overlay containing MTA-owned integration code, tests, license assets, and app changes.
- The patch and source-application scripts used to reconstruct the validation source tree.
- The NewPipe Extractor v0.27.1 upstream source checkout.\n- The FFmpegKit Full 8.1.9 upstream source checkout pinned to v8.1.9-lts-android (LGPL-3.0, non-GPL artifact).
- Exact yt-dlp and Certifi source distributions when their versions are available in the AAR metadata manifest.
- The MTA project GPL license and third-party notices.

## Reconstruct and build
1. Install JDK 21, Android SDK platform 36.1, Android build-tools 36.0.0, Python 3, and Gradle 9.3.1.
2. Extract mta-project-inputs/mta-downloader-nov-17-2026-10-15-48-pm.zip into a directory named project.
3. Copy mta-project-inputs/project-overlay contents into project/.
4. Run python3 mta-project-inputs/tools/patch_media_engine.py project/app/src/main/java/com/example/data/extractor/MediaExtractorEngine.kt from the package root.
5. Build from the reconstructed project directory with gradle --no-daemon testDebugUnitTest lint assembleDebug.
6. For a CycloneDX inventory, run gradle --init-script ../mta-project-inputs/tools/cyclonedx.init.gradle.kts cyclonedxBom from the reconstructed project root.

No production signing key or secrets are included. CI debug artifacts are validation-only.
EOF

mkdir -p "$(dirname "$OUTPUT")"
rm -f "$OUTPUT"
(
  cd "$WORK"
  zip -qr "$OUTPUT" "MTA-DOWNLOADER-CORRESPONDING-SOURCE"
)
echo "Created corresponding source package: $OUTPUT"
