#!/usr/bin/env python3
"""Download exact Python source distributions discovered inside the Android wrapper AAR."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.manifest.is_file():
        print("WARNING: embedded Python package manifest is missing; source sdists were not downloaded.")
        return 0

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    packages = manifest.get("python_distributions", []) if isinstance(manifest, dict) else manifest
    version_hints = manifest.get("version_hints_from_sources", {}) if isinstance(manifest, dict) else {}
    known_names = {package.get("name", "").lower().replace("_", "-").replace(".", "-") for package in packages}
    for name, version in version_hints.items():
        normalized = name.lower().replace("_", "-").replace(".", "-")
        if normalized not in known_names and version:
            packages.append({"name": normalized, "version": version})
    wanted = {"yt-dlp", "certifi"}
    found = set()
    args.output.mkdir(parents=True, exist_ok=True)
    for package in packages:
        name = package.get("name", "").lower().replace("_", "-").replace(".", "-")
        version = package.get("version", "")
        if name not in wanted:
            continue
        if not version or version.lower() in {"unknown", "not_reported"}:
            print("WARNING: no exact version for " + name + "; cannot fetch matching source.")
            continue
        subprocess.run(
            [
                sys.executable, "-m", "pip", "download",
                "--no-deps", "--no-binary=:all:",
                "--dest", str(args.output),
                name + "==" + version,
            ],
            check=True,
        )
        found.add(name)

    missing = wanted - found
    if missing:
        print("WARNING: exact source archives not obtained for: " + ", ".join(sorted(missing)))
    else:
        print("Downloaded exact yt-dlp and Certifi source distributions.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
