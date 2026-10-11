#!/usr/bin/env python3
"""Assemble a separately qualified, immutable COSW + Remotish GitHub Pages demo.

Only Python's standard library is needed. Inputs are pinned by SHA-256.
The canonical COSW release is never modified in place.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "config/releases.lock.json"
EXPECTED_IDS = ("hrashton.remotish", "hrashton.remotish-github-provider")
ALLOWED_DOWNLOAD_HOSTS = frozenset({
    "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"
})
BASE_CONNECT = ("'self'",)
GALLERY_CONNECT = ("'self'", "https://open-vsx.org", "https://openvsx.eclipsecontent.org")
GITHUB_ORIGIN = "https://api.github.com"
MAX_DOWNLOAD = 100 * 1024 * 1024
MAX_UNPACKED = 2 * 1024 * 1024 * 1024
MAX_FILE = 180 * 1024 * 1024
MAX_ENTRIES = 120000
MAX_VSIX_UNPACKED = 40 * 1024 * 1024


class InvalidArtifact(ValueError):
    """An artifact or a deployment policy is not fit for publication."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise InvalidArtifact(message)


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"expected JSON object: {path}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_asset(asset: dict, label: str) -> None:
    require(isinstance(asset, dict), f"invalid {label}")
    tag = asset.get("tag")
    name = asset.get("asset")
    require(isinstance(tag, str) and re.fullmatch(r"v[0-9A-Za-z.-]+", tag) is not None,
            f"invalid tag in {label}")
    require(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9._-]+", name) is not None,
            f"invalid asset filename in {label}")
    url = f"https://github.com/Codellei/{'code-oss-static-web' if label == 'cosw' else 'remotish'}/releases/download/{tag}/{name}"
    require(asset.get("url") == url, f"{label} URL must match pinned Codellei release")
    require(isinstance(asset.get("sha256"), str)
            and re.fullmatch(r"[a-f0-9]{64}", asset["sha256"]) is not None,
            f"{label} SHA-256 is missing or malformed")


def validate_lock(lock: dict) -> None:
    require(lock.get("schemaVersion") == 1, "unsupported release lock")
    check_asset(lock.get("cosw"), "cosw")
    require(re.fullmatch(r"code-oss-static-web-[a-zA-Z0-9.-]+\.tar\.gz",
                         lock["cosw"]["asset"]) is not None, "COSW must be the release tar.gz")
    exts = lock.get("extensions")
    require(isinstance(exts, list) and len(exts) == 2, "require exactly two extensions")
    require(tuple(ext.get("id") for ext in exts if isinstance(ext, dict)) == EXPECTED_IDS,
            "unexpected extension IDs or order")
    for ext in exts:
        check_asset(ext, "extension")
        require(ext.get("asset") in ("remotish.vsix", "remotish-github-provider.vsix"),
                "unexpected VSIX asset name")
        require(ext.get("version") == ext.get("tag", "").lstrip("v"),
                "VSIX version/tag mismatch")
        require(ext.get("license") == "0BSD", "unapproved extension license")
    require(exts[0]["asset"] == "remotish.vsix"
            and exts[1]["asset"] == "remotish-github-provider.vsix",
            "VSIX files must match pinned IDs")


def _url_permitted(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return (parsed.scheme == "https" and parsed.hostname in ALLOWED_DOWNLOAD_HOSTS
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443))


class SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _url_permitted(newurl):
            raise InvalidArtifact("unapproved HTTPS download redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_pinned(asset: dict, cache: Path, *, offline: bool = False) -> Path:
    require(_url_permitted(asset["url"]), "unapproved download URL")
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / (asset["sha256"] + "-" + asset["asset"])
    if dest.is_file() and dest.stat().st_size <= MAX_DOWNLOAD:
        if sha256_file(dest) == asset["sha256"]:
            return dest
    dest.unlink(missing_ok=True)
    if offline:
        raise InvalidArtifact(f"offline asset not available: {asset['asset']}")
    request = urllib.request.Request(asset["url"], headers={
        "User-Agent": "Codellei-cosw-demo/1.0", "Accept": "application/octet-stream"
    })
    opener = urllib.request.build_opener(SafeRedirects)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with opener.open(request, timeout=90) as response, tmp.open("wb") as out:
            require(_url_permitted(response.geturl()), "unapproved download response")
            size = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                require(size <= MAX_DOWNLOAD, "download exceeds size limit")
                out.write(chunk)
        require(sha256_file(tmp) == asset["sha256"], f"SHA-256 mismatch: {asset['asset']}")
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def safe_relative(name: str) -> PurePosixPath:
    require(isinstance(name, str) and name != "" and "\\" not in name and "\x00" not in name,
            "unsafe archive member name")
    require(not name.startswith("/") and not re.match(r"^[a-zA-Z]:", name),
            f"absolute archive path: {name}")
    require(all(part not in ("", ".", "..") for part in name.rstrip("/").split("/")),
            f"archive traversal or ambiguous path: {name}")
    return PurePosixPath(name.rstrip("/"))


def unpack_cosw(archive_path: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    seen: set[str] = set()
    total = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for index, entry in enumerate(archive):
            require(index < MAX_ENTRIES, "COSW archive has too many entries")
            relative = safe_relative(entry.name)
            require(str(relative) not in seen, "duplicate COSW archive entry")
            seen.add(str(relative))
            require(entry.isdir() or entry.isfile(), "COSW tar contains a link or special file")
            target = output.joinpath(*relative.parts)
            if entry.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            require(0 <= entry.size <= MAX_FILE, "COSW file exceeds size limit")
            total += entry.size
            require(total <= MAX_UNPACKED, "COSW uncompressed size limit exceeded")
            target.parent.mkdir(parents=True, exist_ok=True)
            require(not target.exists(), "duplicate or conflicting archive path")
            source = archive.extractfile(entry)
            require(source is not None, "unreadable tar member")
            with source, target.open("xb") as dest:
                shutil.copyfileobj(source, dest, 1024 * 1024)


def add_vsix(vsix_path: Path, ext: dict, output: Path) -> dict:
    dest = output / "extensions" / ext["id"]
    require(not dest.exists(), "extension already present in COSW")
    dest.mkdir(parents=True)
    seen = set()
    total = 0
    with zipfile.ZipFile(vsix_path) as archive:
        entries = archive.infolist()
        require(len(entries) <= 2048, "VSIX has too many entries")
        members = []
        for info in entries:
            relative = safe_relative(info.filename)
            require(str(relative) not in seen, "duplicate VSIX member")
            seen.add(str(relative))
            file_type = (info.external_attr >> 16) & stat.S_IFMT(0o170000)
            require(file_type in (0, stat.S_IFREG, stat.S_IFDIR), "VSIX has a special file")
            require(info.file_size <= 10 * 1024 * 1024, "VSIX member too large")
            total += info.file_size
            require(total <= MAX_VSIX_UNPACKED, "VSIX expansion limit exceeded")
            if relative.parts[0] == "extension" and len(relative.parts) > 1:
                members.append((info, PurePosixPath(*relative.parts[1:])))
        require(any(str(path) == "package.json" for _, path in members),
                "VSIX has no extension/package.json")
        for info, relative in members:
            target = dest.joinpath(*relative.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            require(not target.exists(), "duplicate VSIX extracted path")
            with archive.open(info) as source, target.open("xb") as out:
                shutil.copyfileobj(source, out, 1024 * 1024)
    manifest = read_json(dest / "package.json")
    publisher, name = ext["id"].split(".", 1)
    require(manifest.get("publisher") == publisher and manifest.get("name") == name,
            "VSIX publisher/name differs from lock")
    require(manifest.get("version") == ext["version"], "VSIX version differs from lock")
    require(manifest.get("license") == ext["license"], "VSIX license differs from lock")
    browser = manifest.get("browser")
    require(isinstance(browser, str) and browser != "", "not a browser extension")
    entry = safe_relative(browser.removeprefix("./"))
    require((dest.joinpath(*entry.parts)).is_file(), "browser entrypoint missing")
    require(not manifest.get("enabledApiProposals"), "unstable proposed API cannot be enabled")
    if ext["id"] == EXPECTED_IDS[1]:
        require(manifest.get("extensionDependencies") == [EXPECTED_IDS[0]],
                "GitHub provider must depend on pinned Remotish host")
    return {"id": ext["id"], "version": ext["version"],
            "path": f"extensions/{ext['id']}/", "browserCompatible": True,
            "license": ext["license"]}


def render_policy(site: Path) -> None:
    runtime = read_json(site / "runtime.json")
    require(runtime.get("telemetry") is False, "COSW telemetry is not disabled")
    require(runtime.get("webviews", {}).get("mode") == "disabled",
            "demo cannot enable webviews")
    mode = runtime.get("gallery", {}).get("mode")
    require(mode in ("disabled", "open-vsx"), "unknown COSW gallery mode")
    index_path = site / "index.html"
    index = index_path.read_text(encoding="utf-8")
    match = re.search(
        r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', index
    )
    require(match is not None, "expected CSP meta tag missing")
    csp = match.group(1)
    directives = {}
    for part in csp.split(";"):
        words = part.strip().split()
        if not words:
            continue
        require(words[0] not in directives, "duplicate CSP directive")
        directives[words[0]] = words[1:]
    require(directives.get("default-src") == ["'self'"], "unsafe default CSP")
    require(directives.get("object-src") == ["'none'"], "unsafe object CSP")
    require(directives.get("base-uri") == ["'self'"], "unsafe base URI")
    require("'unsafe-eval'" not in directives.get("script-src", []), "unsafe eval")
    sources = GALLERY_CONNECT if mode == "open-vsx" else BASE_CONNECT
    require(tuple(directives.get("connect-src", ())) == sources,
            "COSW CSP differs from pinned expected profile")
    new_source = " ".join([*sources, GITHUB_ORIGIN])
    old = "connect-src " + " ".join(sources) + ";"
    replacement = "connect-src " + new_source + ";"
    require(csp.count(old) == 1, "ambiguous CSP update")
    index_path.write_text(index.replace(old, replacement, 1), encoding="utf-8")
    bootstrap_path = site / "static-bootstrap.mjs"
    bootstrap = bootstrap_path.read_text(encoding="utf-8")
    marker = "'workbench.startupEditor': 'none'"
    require(bootstrap.count(marker) == 1, "COSW default settings contract changed")
    bootstrap = bootstrap.replace(
        marker, marker + ",\n    'workbench.colorTheme': 'Default Dark+'", 1
    )
    marker = "const config = {"
    require(bootstrap.count(marker) == 1, "COSW bootstrap contract changed")
    default_repo = (
        "if (!initialWorkspace) {\n"
        "  initialWorkspace = {\n"
        "    folderUri: { scheme: 'remotish-github', authority: 'open',\n"
        "      path: '/v1/octocat/Hello-World' }\n"
        "  };\n"
        "}\n"
    )
    require("const WORKSPACE_KEY = 'cosw.workspace.v1';" in bootstrap,
            "COSW workspace persistence contract changed")
    bootstrap = bootstrap.replace(marker, default_repo + marker, 1)
    require("enableTelemetry: false" in bootstrap and "invalid.invalid" in bootstrap,
            "COSW security bootstrap contract changed")
    bootstrap_path.write_text(bootstrap, encoding="utf-8")


def assemble(cosw_tar: Path, vsix_files: list[Path], output: Path, lock: dict) -> None:
    validate_lock(lock)
    require(len(vsix_files) == 2, "need two VSIX files")
    for asset, file in zip([lock["cosw"], *lock["extensions"]], [cosw_tar, *vsix_files]):
        require(file.stat().st_size <= MAX_DOWNLOAD and sha256_file(file) == asset["sha256"],
                f"invalid pinned digest: {asset['asset']}")
    require(not output.is_symlink(), "output must not be a symlink")
    require(output != ROOT and ROOT in output.parents, "output must be inside repo")
    with tempfile.TemporaryDirectory(prefix=".cosw-demo-", dir=ROOT) as temporary:
        stage = Path(temporary) / "site"
        unpack_cosw(cosw_tar, stage)
        require((stage / "out/vs/workbench/workbench.web.main.internal.js").is_file(),
                "COSW web runtime entrypoint missing")
        require((stage / "out/vs/workbench/workbench.web.main.internal.css").is_file(),
                "COSW web stylesheet missing")
        for name in ("additional-extensions.json", "extensions.json", "locked-extensions.json",
                     "deployment-profile.json", "static-bootstrap.mjs", "runtime.json"):
            require((stage / name).is_file(), f"COSW contract file missing: {name}")
        additional = read_json(stage / "additional-extensions.json")
        builtins = read_json(stage / "extensions.json")
        locked = read_json(stage / "locked-extensions.json")
        require(additional == {"schemaVersion": 1, "extensions": []},
                "demo expects clean COSW extension list")
        require(locked == {"schemaVersion": 1, "extensions": []},
                "demo cannot replace COSW approved lock entries")
        require(builtins.get("schemaVersion") == 1
                and isinstance(builtins.get("extensions"), list), "invalid COSW extension index")
        render_policy(stage)
        installed = [add_vsix(file, ext, stage)
                     for file, ext in zip(vsix_files, lock["extensions"])]
        additional["extensions"] = [{"id": entry["id"], "path": entry["path"]}
                                    for entry in installed]
        builtins["extensions"].extend(installed)
        (stage / "additional-extensions.json").write_text(
            json.dumps(additional, indent=2) + "\n", encoding="utf-8"
        )
        (stage / "extensions.json").write_text(
            json.dumps(builtins, indent=2) + "\n", encoding="utf-8"
        )
        provenance = {
            "schemaVersion": 1, "kind": "derived-COSW-demo-not-canonical-release",
            "cosw": {key: lock["cosw"][key] for key in ("tag", "sha256", "url")},
            "extensions": [{"id": x["id"], "version": x["version"],
                            "sha256": x["sha256"], "url": x["url"]}
                           for x in lock["extensions"]],
            "networkExtraOrigins": [GITHUB_ORIGIN],
            "defaultPublicRepository": "octocat/Hello-World",
            "defaultTheme": "Default Dark+",
            "sourceCommit": os.environ.get("GITHUB_SHA", "local-build"),
        }
        (stage / "demo-provenance.json").write_text(
            json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
        )
        if output.exists():
            require(output.is_dir(), "output exists and is not a directory")
            shutil.rmtree(output)
        stage.rename(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="use only SHA-verified cache")
    parser.add_argument("--output", default="_site")
    args = parser.parse_args()
    lock = read_json(LOCK_PATH)
    validate_lock(lock)
    cache = ROOT / ".cache" / "downloads"
    assets = [lock["cosw"], *lock["extensions"]]
    pinned = [fetch_pinned(asset, cache, offline=args.offline) for asset in assets]
    output = (ROOT / args.output).resolve()
    assemble(pinned[0], pinned[1:], output, lock)
    print(f"Qualified-input COSW demo assembled at {output}")


if __name__ == "__main__":
    try:
        main()
    except (InvalidArtifact, OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"demo build failed closed: {exc}") from None
