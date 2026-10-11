#!/usr/bin/env python3
"""Suggest only newer, immutable, SHA-256-addressed upstream release assets.

No branch writes or GitHub API mutation. Intended for unattended, lock-only PRs.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from scripts.build import LOCK_PATH, validate_lock

COSW_RE = re.compile(r"^v(1)\.(\d+)\.(\d+)-web\.(\d+)$")
REMOTISH_RE = re.compile(r"^v(0)\.(1)\.(\d+)-beta\.(\d+)$")
SHA_RE = re.compile(r"^sha256:([a-f0-9]{64})$")
MAX_ASSET_SIZE = 100 * 1024 * 1024


class UpdateError(ValueError):
    pass


def release_version(tag: object, kind: str) -> tuple[int, ...] | None:
    if not isinstance(tag, str):
        return None
    pattern = COSW_RE if kind == "cosw" else REMOTISH_RE
    matched = pattern.fullmatch(tag)
    return tuple(int(n) for n in matched.groups()) if matched else None


def asset_digest(release: dict, name: str) -> str | None:
    matches = [
        x for x in release.get("assets", [])
        if isinstance(x, dict) and x.get("name") == name
        and x.get("state") == "uploaded"
        and isinstance(x.get("size"), int) and 0 < x["size"] <= MAX_ASSET_SIZE
    ]
    if len(matches) != 1:
        return None
    digest = matches[0].get("digest")
    match = SHA_RE.fullmatch(digest) if isinstance(digest, str) else None
    return match.group(1) if match else None


def eligible_release(release: dict, kind: str) -> tuple[tuple[int, ...], dict] | None:
    tag = release.get("tag_name")
    version = release_version(tag, kind)
    if (version is None or release.get("immutable") is not True
            or release.get("draft") is not False
            or not release.get("published_at")):
        return None

    if kind == "cosw":
        name = f"code-oss-static-web-{tag.removeprefix('v')}.tar.gz"
        sha = asset_digest(release, name)
        if sha is None:
            return None
        return version, {
            "tag": tag,
            "asset": name,
            "url": f"https://github.com/Codellei/code-oss-static-web/releases/download/{tag}/{name}",
            "sha256": sha,
        }

    host = asset_digest(release, "remotish.vsix")
    provider = asset_digest(release, "remotish-github-provider.vsix")
    if not host or not provider:
        return None
    entries = []
    for ext_id, filename, sha in (
        ("hrashton.remotish", "remotish.vsix", host),
        ("hrashton.remotish-github-provider", "remotish-github-provider.vsix", provider),
    ):
        entries.append({
            "id": ext_id,
            "version": tag.removeprefix("v"),
            "tag": tag,
            "asset": filename,
            "url": f"https://github.com/Codellei/remotish/releases/download/{tag}/{filename}",
            "sha256": sha,
            "license": "0BSD",
        })
    return version, {"extensions": entries}


def select_update(current: dict, releases: list[dict], kind: str):
    existing_tag = current["cosw"]["tag"] if kind == "cosw" else current["extensions"][0]["tag"]
    old = release_version(existing_tag, kind)
    if old is None:
        raise UpdateError(f"current {kind} lock uses an unsupported release channel")
    available = [entry for r in releases if (entry := eligible_release(r, kind))]
    newer = [entry for entry in available if entry[0] > old]
    return max(newer, key=lambda entry: entry[0])[1] if newer else None


def updated_lock(original: dict, cosw_releases: list[dict], remotish_releases: list[dict]) -> dict:
    validate_lock(original)
    output = copy.deepcopy(original)
    cosw = select_update(original, cosw_releases, "cosw")
    rem = select_update(original, remotish_releases, "remotish")
    if cosw is not None:
        output["cosw"] = cosw
    if rem is not None:
        output["extensions"] = rem["extensions"]
    validate_lock(output)
    return output


def get_releases(repository: str) -> list[dict]:
    url = f"https://api.github.com/repos/Codellei/{repository}/releases?per_page=100"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Codellei-cosw-demo-release-maintenance/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if (token := os.environ.get("GH_TOKEN", "").strip()):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as response:
        result = json.load(response)
    if not isinstance(result, list) or any(not isinstance(x, dict) for x in result):
        raise UpdateError(f"invalid GitHub release list for {repository}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    next_lock = updated_lock(
        original, get_releases("code-oss-static-web"), get_releases("remotish")
    )
    args.output.write_text(json.dumps(next_lock, indent=2) + "\n", encoding="utf-8")
    print("release change proposed" if next_lock != original else "release pins current")


if __name__ == "__main__":
    try:
        main()
    except (UpdateError, OSError, ValueError) as exc:
        sys.exit(f"release discovery failed closed: {exc}")
