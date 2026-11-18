# MTA Downloader — Media Engine Integration Audit

Date: 2026-11-18
Base: MTA-Downloader main at 5a25d2d663a8590fd3e6a1f56ee6a9370c637ae1
Working branch: feature/mta-unified-media-engine

## Decision gate: licensing

The requested upstream projects are not all drop-in Android libraries.

| Project | Intended role | Upstream license / integration note |
|---|---|---|
| yt-dlp | Broad site extraction | Unlicense upstream; Python-based. Android needs a maintained runtime/wrapper and ABI review. |
| NewPipe Extractor | Native extractors for supported services | GPL-3.0-or-later. |
| QuickTube (devgalib/QuickTube) | Reference architecture and integration patterns | GPL-3.0; it integrates NewPipe Extractor and yt-dlp. Do not copy its application code. |
| Seal | Android reference implementation for yt-dlp | GPL-3.0; use as reference, not as an additional engine. |
| XDM (itsolaph/xdm) | Reference for segmented/resumable downloads and browser capture | GPL-3.0-or-later; uses NewPipe Extractor. |

**Integrated first-stage Android wrapper (2026-11-18):** `dev.ffmpegkit-maintained:yt-dlp-android:2.0.2` is now added through the source overlay on the feature branch. It embeds CPython 3.13 through Chaquopy and yt-dlp, supports arm64-v8a and x86_64, and the free build does not include TLS fingerprint impersonation. Page URLs now route to the on-device yt-dlp download path after the existing rewarded-ad callback. The build, SBOM, dependency notices, and device behavior are still unverified; do not merge or ship until CI and device validation pass.

**Owner approval recorded (2026-11-18):** the owner approved distributing MTA Downloader under GPL-3.0-compatible terms and publishing the corresponding source and notices. This approval permits proceeding with the licensing migration, subject to preserving third-party notices and separately reviewing every bundled component.

## Proposed MTA architecture

1. MediaExtractionProvider interface and MediaExtractionRouter with deterministic priority, timeout, cancellation, and normalized errors.
2. YtDlpProvider as an optional provider behind a reviewed Android runtime adapter; no TLS impersonation or DRM circumvention.
3. NewPipeProvider as an optional provider only after GPL approval; never run two extractors concurrently for the same URL by default.
4. BrowserCaptureProvider for public direct media URLs observed in the user's WebView session, retaining safe Referer/User-Agent handling.
5. An MTA-owned download core inspired by XDM: HTTP range validation, bounded parallel segments, durable checkpoints, ETag/Last-Modified validation, pause/resume/retry, queue limits, storage safety, and correct HLS handling.
6. Keep the existing Compose UI, Room history, app identity, signing configuration, and Start.io rewarded-ad flow. The ad completion callback remains the gate before a download starts.

## Safety and correctness constraints

- Only public/direct media the user is authorized to save; do not bypass DRM, private access, paywalls, or account controls.
- Never label .ts, .m4s, HLS segments, or DASH fragments as MP4 without a verified remux.
- Report unsupported, login-only, region-blocked, expired, or protected streams clearly.
- Do not add opaque remote extraction servers or TLS-fingerprint impersonation.
- Do not replace the production signing key or publish CI-signed artifacts.

## Validation plan

- Unit tests for URL parsing, provider selection, timeout/cancellation, MIME/format mapping, and range/ETag resume logic.
- CI: unit tests, lint, debug/release build, dependency/license inventory, APK size and ABI inventory.
- Device validation on Android 12: shared links, in-app browser capture, Start.io reward completion/cancel, download pause/resume, restart recovery, storage playback.
- Live extraction tests use only public test media with permission and are informational when a service blocks CI IPs.


## Verified Android integration candidate

- Artifact: `dev.ffmpegkit-maintained:yt-dlp-android:2.0.2` (Maven Central, MIT metadata).
- Android minimum: API 24; device target Android 12 is compatible by stated minimum.
- ABIs: arm64-v8a and x86_64; the user's Samsung arm64 device is within the supported set.
- Runtime: embedded CPython 3.13 / Chaquopy; expected AAR size approximately 60–80 MB before final APK/AAB packaging.
- Important limitation: free version does not provide TLS fingerprint impersonation. No impersonation or anti-bot bypass feature will be used.
- yt-dlp's source repository is Unlicense, but bundled executable releases may include components under other licenses; use source/PyPI artifacts and preserve all notices, rather than assuming every binary distribution has identical licensing.
- NewPipe Extractor latest observed release during this review: v0.27.1. Pin an exact version and commit before adding it; verify dependency graph and GPL notices.

## Work status at this checkpoint

- Completed: isolated feature branch, GPL-3.0 project license, third-party notice inventory, yt-dlp Android runtime integration, app initialization, shared/page URL routing to the local engine, Room progress updates, MediaStore publication on Android 10+, cancellation interruption, and protection against DownloadManager reconciliation incorrectly failing local jobs.
- CI: the first integration build, tests, application identity checks, signing verification, and artifact upload passed. The latest changes are being rebuilt; see the PR checks before merging.
- Not completed: NewPipe provider, XDM-style segmented/resumable queue, persistent pause/resume controls, dependency SBOM and final package-size review, and physical Android 12 testing.
- Source handling: original ZIP baseline remains unchanged. CI applies reviewed source overlays and a guarded patch to the original MediaExtractorEngine after extraction.
