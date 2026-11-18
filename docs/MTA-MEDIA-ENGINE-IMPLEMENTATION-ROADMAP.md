# MTA Downloader — Ad-free Multi-Engine Roadmap

Date: 2026-11-18
Working branch: feature/multi-engine-adfree
Base commit: 429003d2c1d3a8c618f77ed1f160caa483f6a914

## Product requirement

MTA Downloader is ad-free. No advertising SDK, advertising identifier, ad initialization, rewarded-ad callback, ad-only screen, or watch-an-ad download gate may remain. After the user selects an available format, the download starts directly. Preserve unrelated app functionality.

## Correct roles of the requested projects

| Project | Role | MTA integration approach |
|---|---|---|
| yt-dlp | Multi-site extractor | Existing on-device Android runtime; broad-coverage provider |
| NewPipe Extractor | Native extraction library | Independent provider after API, dependency, and GPL review |
| QuickTube | Android reference application | Study its NewPipe → page parser → yt-dlp fallback design; do not copy the app wholesale |
| Seal | yt-dlp Android front-end/reference | Use ideas such as playlists, subtitles, metadata and command options; do not use Seal branding or name |
| XDM | Download manager/reference | Adopt segmented HTTP, retry, pause/resume and queue concepts; it is not an extractor |

## Target architecture

1. Common media extraction provider contract with cancellation and bounded timeouts.
2. Deterministic router that avoids concurrent duplicate extraction for one URL.
3. Browser media parser for public direct media URLs observed in the user's own browser session; recognize MP4/WebM/audio, HLS playlists and DASH manifests.
4. NewPipe provider for supported services using a pinned NewPipe Extractor API.
5. yt-dlp provider as broad-coverage on-device fallback.
6. MTA-owned download manager with validated HTTP ranges, bounded parallel segments, ETag/Last-Modified checks, durable checkpoints, pause/resume/retry, queue limits, safe assembly and Android storage publication.
7. Normalized format model shared by quality selection and download history.

## Routing and correctness

Browser-captured direct media → NewPipe → yt-dlp → explicit unsupported result. Never invent resolutions, sizes, MIME types, or extensions. HLS/DASH manifests and fragments must not be mislabeled as MP4; remux only after a verified local operation. Report unsupported, login-only, region-blocked, expired and protected streams clearly.

## Licensing and safety

Keep GPL-3.0-or-later and provide corresponding source and notices for shipped components. Verify exact versions and license compatibility before incorporating code from GPL-family references. QuickTube, Seal and XDM are reference applications, not independent extractor binaries to bundle. Do not use Seal branding. No DRM circumvention, private-content access, paywall bypass, account-control bypass, or TLS fingerprint impersonation.

## Verification

- Static scan: no Start.io/StartApp, AD_ID, ad SDK coordinates, identifiers, reward callbacks or ad gate in source, manifest, Gradle or patch scripts.
- Tests: URL classification, normalized formats, router order/fallback, timeout/cancellation, HLS/DASH detection, range/ETag resume and no-ad invariant.
- CI: tests, lint, debug/release builds, dependency inventory, SBOM, APK/AAB size and ABI review.
- Physical Android 12 tests: shared links, browser capture, immediate download, pause/resume, restart recovery, storage and playback.
- Preserve production signing key; never distribute CI-signed builds as production updates.

## Status at this commit

- Existing: yt-dlp Android dependency and initialization in the overlay; baseline ZIP remains unchanged.
- Corrected: removed Start.io dependency, app-ID metadata, AD_ID permission and SDK initialization from the overlay; renamed the repository download method to remove the rewarded-ad requirement.
- Not yet complete: audit/remove all ad references from extracted baseline and every patch script; implement and wire BrowserMediaParser, NewPipeProvider, router and resumable download manager; add tests and validate CI.
- No NewPipe provider, XDM-style segmented manager, physical device test or release artifact is claimed complete until implemented and verified.
