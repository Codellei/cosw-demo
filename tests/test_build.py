"""Offline fixtures exercise the trust boundary without contacting GitHub."""
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build import (InvalidArtifact, assemble, safe_relative,
                           validate_lock, _url_permitted)

HOST = "hrashton.remotish"
PROVIDER = "hrashton.remotish-github-provider"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def asset(name, data, tag="v0.1.0-beta.15"):
    repo = "code-oss-static-web" if name.endswith(".tar.gz") else "remotish"
    return {"tag": tag, "asset": name, "sha256": digest(data),
            "url": f"https://github.com/Codellei/{repo}/releases/download/{tag}/{name}"}


def tar_bytes(*, path="index.html", symlink=False):
    html = (
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'self\'; base-uri \'self\'; object-src \'none\'; '
        'script-src \'self\' blob:; connect-src \'self\';">'
    ).encode()
    bootstrap = (
        "const WORKSPACE_KEY = 'cosw.workspace.v1';\n"
        "let initialWorkspace;\n"
        "const config = {\n"
        "  workspaceProvider: { workspace: initialWorkspace },\n"
        "  configurationDefaults: { 'workbench.startupEditor': 'none' },\n"
        "  productConfiguration: { enableTelemetry: false, "
        "webviewContentExternalBaseUrlTemplate: 'https://invalid.invalid' }\n"
        "};\n"
    ).encode()
    files = {
        "index.html": html,
        "static-bootstrap.mjs": bootstrap,
        "runtime.json": json.dumps({"telemetry": False, "webviews": {"mode": "disabled"},
                                   "gallery": {"mode": "disabled"}}).encode(),
        "additional-extensions.json": b'{"schemaVersion":1,"extensions":[]}',
        "locked-extensions.json": b'{"schemaVersion":1,"extensions":[]}',
        "extensions.json": b'{"schemaVersion":1,"extensions":[]}',
        "deployment-profile.json": b'{"schemaVersion":1,"id":"baseline-static"}',
        "out/vs/workbench/workbench.web.main.internal.js": b"// fixture",
        "out/vs/workbench/workbench.web.main.internal.css": b"/* fixture */",
    }
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        for filename, content in files.items():
            info = tarfile.TarInfo(path if filename == "index.html" else filename)
            if symlink and filename == "index.html":
                info.type = tarfile.SYMTYPE
                info.linkname = "static-bootstrap.mjs"
            else:
                info.size = len(content)
            tar.addfile(info, io.BytesIO(content) if not (symlink and filename == "index.html")
                        else None)
    return out.getvalue()


def vsix_bytes(extid, *, proposed=False, wrong_dependency=False):
    publisher, name = extid.split(".", 1)
    manifest = {"publisher": publisher, "name": name, "version": "0.1.0-beta.15",
                "license": "0BSD", "browser": "./dist/extension.js"}
    if extid == PROVIDER:
        manifest["extensionDependencies"] = ["someone.else"] if wrong_dependency else [HOST]
    if proposed:
        manifest["enabledApiProposals"] = ["timeline"]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("extension/package.json", json.dumps(manifest))
        archive.writestr("extension/dist/extension.js", "exports.activate = () => {};")
    return out.getvalue()


def make_lock(cosw, host, provider):
    return {"schemaVersion": 1,
            "cosw": asset("code-oss-static-web-v0.1.0-beta.15.tar.gz", cosw),
            "extensions": [
                {"id": HOST, "version": "0.1.0-beta.15", "license": "0BSD",
                 **asset("remotish.vsix", host)},
                {"id": PROVIDER, "version": "0.1.0-beta.15", "license": "0BSD",
                 **asset("remotish-github-provider.vsix", provider)}]}


class AssemblerTests(unittest.TestCase):
    def test_reject_archive_paths(self):
        for path in ("../evil", "/absolute", "C:/drive", "./dot", "x//y",
                     "x\\y", "x/../evil"):
            with self.subTest(path=path):
                with self.assertRaises(InvalidArtifact):
                    safe_relative(path)

    def test_download_host_allowlist(self):
        self.assertTrue(_url_permitted("https://github.com/a/b"))
        self.assertTrue(_url_permitted("https://release-assets.githubusercontent.com/file"))
        for url in ("http://github.com/a", "https://evil.example/a",
                    "https://github.com.evil.example/a",
                    "https://github.com:8080/a", "https://person@github.com/a"):
            self.assertFalse(_url_permitted(url), url)

    def _run(self, *, symlink=False, traversal=False, proposed=False,
             wrong_dependency=False, corrupt=False):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            root = Path(tmp)
            cosw = tar_bytes(path="../index.html" if traversal else "index.html",
                             symlink=symlink)
            host = vsix_bytes(HOST, proposed=proposed)
            provider = vsix_bytes(PROVIDER, wrong_dependency=wrong_dependency)
            lock = make_lock(cosw, host, provider)
            files = []
            for name, data in (("cosw.tar.gz", cosw), ("host.vsix", host),
                               ("provider.vsix", provider)):
                file = root / name
                file.write_bytes(data + b"bad" if corrupt and name == "host.vsix" else data)
                files.append(file)
            output = root / "site"
            assemble(files[0], files[1:], output, lock)
            return {
                "index": (output / "index.html").read_text(),
                "bootstrap": (output / "static-bootstrap.mjs").read_text(),
                "additional": json.loads((output / "additional-extensions.json").read_text()),
                "locked": json.loads((output / "locked-extensions.json").read_text()),
                "manifest": json.loads((output / "demo-provenance.json").read_text())
            }

    def test_builds_derived_demo_and_leaves_canonical_lock_intact(self):
        output = self._run()
        self.assertIn("connect-src 'self' https://api.github.com;", output["index"])
        self.assertIn("Default Dark+", output["bootstrap"])
        self.assertIn("octocat/Hello-World", output["bootstrap"])
        self.assertIn("demoRequestedWorkspace", output["bootstrap"])
        self.assertIn("history.replaceState", output["bootstrap"])
        self.assertIn("repos.length + folders.length !== 1", output["bootstrap"])
        self.assertEqual([HOST, PROVIDER],
                         [x["id"] for x in output["additional"]["extensions"]])
        self.assertEqual(output["locked"], {"schemaVersion": 1, "extensions": []})
        self.assertEqual(output["manifest"]["networkExtraOrigins"],
                         ["https://api.github.com"])

    def test_rejects_symlink_traversal_proposed_api_and_wrong_dependency(self):
        for kwargs in ({"symlink": True}, {"traversal": True}, {"proposed": True},
                       {"wrong_dependency": True}, {"corrupt": True}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(InvalidArtifact):
                    self._run(**kwargs)

    def test_rejects_unexpected_lock_and_unpinned_url(self):
        cosw, host, provider = tar_bytes(), vsix_bytes(HOST), vsix_bytes(PROVIDER)
        lock = make_lock(cosw, host, provider)
        lock["extensions"][0]["url"] = "https://evil.example/x.vsix"
        with self.assertRaises(InvalidArtifact):
            validate_lock(lock)


if __name__ == "__main__":
    unittest.main()
