# Third-Party Notices — MTA Downloader

MTA Downloader is distributed under GNU GPL version 3 or (at your option) any later version. See LICENSE.

This inventory distinguishes runtime dependencies from architectural references. A reference-only project is not part of the APK.

| Project | Upstream | Role | License reported upstream | Status |
|---|---|---|---|---|
| yt-dlp | https://github.com/yt-dlp/yt-dlp | Site extraction core | Unlicense (inspect bundled components separately) | Used through Android wrapper |
| yt-dlp-android | https://github.com/ffmpegkit-maintained/yt-dlp-android | Android runtime wrapper | MIT | Declared; build verification pending |
| NewPipe Extractor v0.27.1 | https://github.com/TeamNewPipe/NewPipeExtractor | Native site extractors for YouTube, SoundCloud, media.ccc.de, PeerTube and Bandcamp | GPL-3.0-or-later | Added as pinned dependency and wired as the first native page provider; CI verification pending |
| QuickTube | https://github.com/devgalib/QuickTube | Reference extraction architecture | GPL-3.0 | Reference only |
| Seal | https://github.com/JunkFood02/Seal | yt-dlp Android workflow reference | GPL-3.0 | Reference only; do not use Seal branding |
| Android XDM reference | https://github.com/itsolaph/xdm | Segmented/resumable download manager reference | Verify exact revision before copying code | Reference only |

## Requirements before shipping

- Pin every shipped dependency to an exact version and commit where applicable.
- Preserve upstream copyright notices and full applicable license texts.
- Record modifications and provide corresponding source/build scripts for shipped binaries.
- Provide source access alongside each distributed APK/AAB as required by GPLv3 section 6.
- Generate a complete SBOM and transitive license inventory, including native and bundled runtime components.
- Add an in-app open-source licenses screen and source-code link.
- This project intentionally excludes advertising SDKs.

## Product constraints

- Do not bypass DRM, private access, paywalls, or account controls.
- Do not bundle TLS fingerprint impersonation or anti-bot evasion.
- Do not mislabel HLS/DASH fragments as MP4.
- Preserve production signing key and verify release certificates. Never distribute CI-signed builds as production updates.
