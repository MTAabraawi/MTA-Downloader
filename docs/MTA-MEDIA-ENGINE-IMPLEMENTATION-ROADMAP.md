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

- **Ad-free invariant:** the CI source scan passes. Start.io/StartApp dependency, app ID metadata, AD_ID permission and initialization are absent from the assembled source; the download flow no longer has a rewarded-ad gate.
- **NewPipe Extractor v0.27.1:** pinned and integrated as a native provider for supported services, with an OkHttp downloader adapter. Java/Kotlin bytecode targets are aligned to Java 17, as required by this release line.
- **MediaExtractionRouter:** native provider requests are bounded by a timeout and duplicate URL requests are serialized with a short-lived result cache. Unsupported URLs continue through the existing page parser and yt-dlp fallback.
- **BrowserMediaParser:** direct video/audio files are classified separately from HLS/DASH manifests. Manifests are not passed to the direct-file downloader as if they were MP4 files.
- **Subtitles:** NewPipe subtitle streams are exposed as selectable formats; yt-dlp fallback has a subtitle-only option for normal and automatic subtitles in VTT/best format.
- **Playlists:** yt-dlp is switched to playlist mode when a playlist URL is detected. Output files are enumerated recursively and each completed media item receives its own download-history row.
- **Large direct downloads:** the segmented downloader uses bounded 8 MiB ranges, up to four parallel segments, strict Content-Range checks, ETag/Last-Modified validation, three retries and a durable checkpoint. It is selected only for large files whose origin supports validated ranges; otherwise Android DownloadManager remains the fallback.
- **CI verification:** unit tests, lint and assembleDebug all passed in run [44332978517](https://github.com/MTAabraawi/MTA-Downloader/actions/runs/44332978517). This was a CI validation build only, not a release or a device-test package.
- **Still outstanding:** explicit pause/resume controls and a durable user-visible queue; restoring browser-captured request headers/cookies safely for protected-by-session public streams; broader provider coverage and real service fixture tests; SBOM/transitive license review and open-source notices UI; release build and signing review.
- **No physical-device testing or user APK testing has been performed.** Per the agreed sequence, do not ask the user to install a version until the complete integration is finished and the final merge is approved.

## Next implementation order

1. Complete explicit queue, pause/resume and restart recovery around the segmented engine without replacing existing DownloadManager behavior.
2. Carry only necessary, user-session browser headers into supported downloads, with secure handling and no credential logging.
3. Add deterministic tests for playlist item accounting, subtitle outputs, router fallback/cancellation and range-resume recovery.
4. Complete dependency/SBOM and GPL source-distribution review.
5. Run full CI on the final branch state; only then prepare a single consolidated build for the post-merge test stage.
