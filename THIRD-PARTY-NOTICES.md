# Third-Party Notices — MTA Downloader

MTA Downloader is distributed under GNU GPL version 3 or (at your option) any later version. See `LICENSE`.

This file records upstream projects evaluated for the unified media engine. Listing a project here does not claim that its code or binaries have already been incorporated into the current APK. The exact version, commit, license text, modifications, and corresponding source must be recorded for every component actually shipped.

| Project | Upstream | Role considered | License reported by upstream | Integration status |
|---|---|---|---|---|
| yt-dlp | https://github.com/yt-dlp/yt-dlp | Site extraction core bundled by Android wrapper | Unlicense (upstream source) | Integrated transitively via yt-dlp-android 2.0.2; bundled component inventory still required |
| yt-dlp-android | https://github.com/ffmpegkit-maintained/yt-dlp-android | Android runtime wrapper for yt-dlp | MIT | Added in feature branch; CI/build validation pending |\n| NewPipe Extractor | https://github.com/TeamNewPipe/NewPipeExtractor | Native site extractors | GPL-3.0-or-later | Evaluated; not integrated |
| QuickTube | https://github.com/devgalib/QuickTube | Reference architecture only | GPL-3.0-or-later | Reference only; do not copy app branding/assets |
| Seal | https://github.com/JunkFood02/Seal | Android yt-dlp integration reference | GPL-3.0 | Reference only; do not use Seal name or branding |
| XDM | https://github.com/itsolaph/xdm | Download manager architecture reference | Verify exact upstream revision before use | Reference only; not yet integrated |

## Required before shipping an engine component

- Pin the upstream repository, release/tag, and exact commit SHA.
- Preserve the upstream copyright and license notices; include the full applicable license text.
- Record every local modification and its date.
- Include all corresponding source needed to build, install, run, and modify the shipped binaries, including native libraries, Python/runtime packaging, FFmpeg/aria2 binaries, build scripts, and patches where applicable.
- Provide source access alongside each distributed APK/AAB in a way that satisfies GPLv3 section 6; do not rely on a temporary CI artifact as the sole source offer.
- Generate a complete SBOM and license inventory for transitive dependencies and bundled binaries.
- Add an in-app About → Open-source licenses screen and a clear source-code link.
- Confirm advertising SDK terms and other proprietary SDK licenses separately. GPL approval does not relicense Start.io or grant rights to redistribute its SDK outside its own terms.

## Product and platform constraints

- Do not use DRM circumvention, private-content access, paywall bypass, or account-control bypass.
- Do not bundle TLS fingerprint impersonation intended to evade platform protections.
- Do not claim YouTube downloading is supported where platform terms or distribution-channel policies prohibit it; channel-specific builds may require disabling that feature.
- Do not ship any CI-signed APK as a production update. Preserve the existing production signing key and verify its certificate after release builds.

## Notice maintenance

Update this file on every dependency change. Remove projects that are not shipped from the shipped-components inventory, and distinguish development-only tools from runtime components.