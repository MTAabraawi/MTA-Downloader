# MTA Downloader — dependency adoption decisions

This document records the engineering decision for every library suggested for the downloader. The goal is to add working capabilities without duplicate frameworks, unused dependencies, or destabilizing the existing Android app.

## Integrated in this change set

| Library | Pinned version | Decision and use |
|---|---:|---|
| Retrofit | 3.0.0 | Added for suspend-based public page requests, reusing the app's existing OkHttp client and timeout/redirect policy. |
| Jsoup | 1.24.1 | Added directly and used for HTML5/OpenGraph metadata and video/source extraction. Parser unit tests cover attribute order, entity decoding, and relative URLs. |
| AndroidX Media3 ExoPlayer + UI | 1.11.1 | Replaces the platform VideoView in the in-app player. The new player releases resources and pauses/resumes with lifecycle events. |
| FFmpegKit Full (maintained fork) | 8.1.9 | Adds on-device audio/video muxing and post-processing through the LGPL-only, non-GPL artifact. A separate processing service uses argv arguments rather than shell command concatenation. |

## Retained existing libraries

- **OkHttp** remains the shared transport and the underlying Retrofit client. The segmented downloader and existing extractor code still use it directly.
- **Coil 2.7.0** remains the production Compose image loader. Glide Compose's public integration is still beta; no benchmark or compatibility test demonstrates that replacing the existing working Coil path is better. Adding both image loaders would duplicate caches and increase APK size. Glide is therefore not added as an unused second loader.
- **Jetpack Compose LazyColumn/LazyRow/LazyVerticalGrid** remain the list framework. Android's RecyclerView release documentation explicitly recommends Compose for new UI and marks RecyclerView as maintenance-only. RecyclerView is not added as an unused dependency.

## Tencent Shadow — compatibility gate, not a blind dependency

Tencent Shadow is a multi-module dynamic plugin framework (host, loader, runtime, manager, plugin build tooling and plugin packaging), not a single drop-in library. Its published release notes document compatibility work through AGP 8.9, while this app currently builds with AGP 9.1.1. Adding only one Shadow module would not create a working plugin system and could break the app's build.

Shadow integration is therefore gated on a separate isolated proof-of-concept that must:
1. build a host and signed sample plugin against this exact AGP/Gradle/JDK matrix;
2. verify plugin signatures and SHA-256 before install/load;
3. enforce a signed allowlist, version compatibility and rollback;
4. reject arbitrary code packages and keep plugins from changing downloader permissions or accessing private content;
5. pass instrumentation tests on Android 12 and newer.

Until those gates pass, no Tencent Shadow artifacts are added to the production dependency graph.

## Product invariants

- Do not reintroduce any advertising SDK, ad identifier, ad permission, or rewarded-ad flow.
- Do not remove any existing dependency merely because a new dependency was added.
- Keep the current Compose UI and database architecture intact.
- No release signing, production publishing, or merge to main is performed by this validation workflow.
