#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "\${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="\${1:-\${REPO_ROOT}/MTA-DOWNLOADER-CORRESPONDING-SOURCE.zip}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

BUNDLE="$WORK/MTA-DOWNLOADER-CORRESPONDING-SOURCE"
mkdir -p "$BUNDLE/mta-project-inputs" "$BUNDLE/upstream/NewPipeExtractor"

cp "$REPO_ROOT/mta-downloader-nov-17-2026-10-15-48-pm.zip" "$BUNDLE/mta-project-inputs/"
cp -a "$REPO_ROOT/project-overlay" "$BUNDLE/mta-project-inputs/"
cp -a "$REPO_ROOT/tools" "$BUNDLE/mta-project-inputs/"
cp -a "$REPO_ROOT/docs" "$BUNDLE/mta-project-inputs/"
cp "$REPO_ROOT/LICENSE" "$BUNDLE/"
cp "$REPO_ROOT/THIRD-PARTY-NOTICES.md" "$BUNDLE/"

git clone --depth 1 --branch v0.27.1 https://github.com/TeamNewPipe/NewPipeExtractor.git "$BUNDLE/upstream/NewPipeExtractor"
printf "NewPipe Extractor v0.27.1 commit: %s\\n" "$(git -C "$BUNDLE/upstream/NewPipeExtractor" rev-parse HEAD)" > "$BUNDLE/UPSTREAM-VERSIONS.txt"

cat > "$BUNDLE/BUILDING.md" <<'EOF'
# MTA Downloader corresponding source package

This source package accompanies the GPL-3.0-or-later MTA Downloader build that uses NewPipe Extractor v0.27.1.

## Included material
- The exact original Android project source archive used by the CI validation workflow.
- The reviewed project overlay containing MTA-owned integration code, tests, license assets, and app changes.
- The patch and source-application scripts used to reconstruct the validation source tree.
- The NewPipe Extractor v0.27.1 upstream source checkout.
- The MTA project GPL license and third-party notices.

## Reconstruct and build
1. Install JDK 21, Android SDK platform 36.1, Android build-tools 36.0.0, Python 3, and Gradle 9.3.1.
2. Extract the original source archive into a directory named project.
3. Copy the included project-overlay contents into project/.
4. Run python3 tools/patch_media_engine.py project/app/src/main/java/com/example/data/extractor/MediaExtractorEngine.kt from the package root.
5. Build from the reconstructed project directory with gradle --no-daemon testDebugUnitTest lint assembleDebug.
6. For a CycloneDX inventory, run gradle --init-script ../tools/cyclonedx.init.gradle.kts cyclonedxBom from the reconstructed project root.

No production signing key or secrets are included. CI debug artifacts are validation-only.
EOF

mkdir -p "$(dirname "$OUTPUT")"
rm -f "$OUTPUT"
(
  cd "$WORK"
  zip -qr "$OUTPUT" "MTA-DOWNLOADER-CORRESPONDING-SOURCE"
)
echo "Created corresponding source package: $OUTPUT"
