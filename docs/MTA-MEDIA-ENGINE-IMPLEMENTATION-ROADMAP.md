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

- **Ad-free invariant:** the CI source scan passes. Start.io/StartApp dependency, app ID metadata, AD_ID permission and initialization are absent from the assembled source; the download flow starts directly after format selection.
- **NewPipe Extractor v0.27.1:** pinned and integrated as a native provider for services recognized by NewPipe, using an OkHttp downloader adapter and ordinary TLS behavior. Extracted fields include title, uploader, views, duration, thumbnail, audio/video formats and available subtitle streams.
- **MediaExtractionRouter:** native extraction requests run on IO with a bounded timeout, per-URL serialization and a short-lived result cache. Unsupported pages continue through the existing HTML parser and on-device yt-dlp fallback.
- **Browser capture:** direct video/audio files and HLS/DASH manifests are classified separately. Browser request headers are filtered to a small allowlist, credential-bearing headers are excluded, and the safe snapshot is stored in Room with a v1-to-v2 migration for retry/resume.
- **Direct media formats:** audio/video recognition and MIME/extension inference cover common formats including MP4, WebM, MOV, MKV, FLV, MP3, M4A, AAC, WAV, OGG and Opus. This does not imply every codec/container combination has been playback-tested.
- **HLS/DASH and playlists:** captured manifests are routed to yt-dlp rather than treated as MP4 files. Playlist URLs are detected and downloaded with playlist mode; produced files are enumerated recursively and recorded individually. This is implementation-level integration; broad live-site compatibility still requires fixture and device verification.
- **Subtitles:** NewPipe subtitle streams are exposed as selectable formats. The yt-dlp fallback supports normal and automatic subtitle-only downloads in VTT/best format.
- **XDM-style direct downloads:** large files use bounded 8 MiB HTTP ranges, up to four parallel segments, Content-Range validation, strong ETag or Last-Modified If-Range validation, three retries and durable checkpoints. Weak ETags are not used as If-Range validators; Last-Modified is preferred when available. Unsupported or small range downloads fall back to Android DownloadManager.
- **Queue and recovery:** Room-backed download history, bounded concurrent segmented tasks, pause/resume controls and restart recovery for incomplete segmented jobs are implemented. Incomplete segmented jobs are made resumable; interrupted yt-dlp jobs without durable checkpoints are marked failed for retry. Pause/resume applies to the segmented direct-download path; yt-dlp tasks remain non-pausable through this UI.
- **Browser capture safety:** parser rejects private/reserved IPv4 and IPv6 literal hosts; tests cover loopback, private, link-local, carrier-grade NAT and IPv6 local ranges. If no safe media candidate exists, the UI reports that explicitly instead of creating an empty quality list.
- **CI verification:** latest run [44341590198](https://github.com/MTAabraawi/MTA-Downloader/actions/runs/44341590198) passed all stages including source application, ad-free invariant, unit tests, lint, debug APK assembly and artifact upload. Test reports show **15 tests passed, 0 failures, 0 errors, 0 skipped**. Lint reports **0 errors and 74 warnings**. The uploaded debug APK is validation-only and has not been installed on a device.
- **Still outstanding:** real service fixtures for NewPipe and yt-dlp routing; end-to-end HLS/DASH and playlist output tests; broader metadata and format normalization; dependency/SBOM/transitive-license audit and complete GPL source-distribution package; in-app open-source notices; release signing and production build review.
- **No physical-device testing or user APK testing has been performed.** Per the agreed sequence, do not ask the user to install a version until the integration is complete, final CI passes and the merge is approved.

## Next implementation order

1. Complete deterministic integration tests for playlist item accounting, subtitle outputs, router fallback/cancellation and range-resume recovery.
2. Complete dependency/SBOM and GPL source-distribution review, including transitive native/FFmpeg components.
3. Add in-app open-source notices and corresponding source/license access.
4. Run full CI on the final branch state; only then prepare a single consolidated build for the post-merge test stage.
