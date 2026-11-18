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

The Android wrapper commonly used with yt-dlp (yausername/youtubedl-android) is also GPL-3.0 and bundles Python/native components. A different MIT-licensed wrapper exists, but its published architecture bundles a 60–80 MB Python runtime and has a materially larger ABI footprint; it needs independent security, provenance, and license review before use.

**Do not copy or link GPL components into the existing app until the owner explicitly chooses a GPL-compatible distribution model and agrees to publish the corresponding source and notices.** This is a distribution/licensing decision, not a technical build detail.

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
