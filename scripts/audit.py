#!/usr/bin/env python3
"""Independent fail-closed output guard for the public Pages artifact."""
import json
import re
import sys
from pathlib import Path

from scripts.build import EXPECTED_IDS, GALLERY_CONNECT, BASE_CONNECT, GITHUB_ORIGIN

site = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
assert site.is_dir() and not site.is_symlink(), "site missing or symlinked"
assert not any(path.is_symlink() for path in site.rglob("*")), "site contains symlinks"
def load(name):
    return json.loads((site / name).read_text())

runtime = load("runtime.json")
assert runtime.get("telemetry") is False
assert runtime.get("webviews", {}).get("mode") == "disabled"
mode = runtime.get("gallery", {}).get("mode")
assert mode in ("disabled", "open-vsx")
expected = GALLERY_CONNECT if mode == "open-vsx" else BASE_CONNECT
text = (site / "index.html").read_text()
match = re.search(r"(?:^|;)\s*connect-src\s+([^;]+);", text)
assert match and match.group(1).split() == [*expected, GITHUB_ORIGIN], "unsafe connect-src"
assert "default-src 'self';" in text and "object-src 'none';" in text
assert "'unsafe-eval'" not in text
bootstrap = (site / "static-bootstrap.mjs").read_text()
assert "'workbench.colorTheme': 'Default Dark+'" in bootstrap
assert ("enableTelemetry: false" in bootstrap or "enableTelemetry: runtime.telemetry === true" in bootstrap)
assert "invalid.invalid" in bootstrap
assert "/v1/octocat/Hello-World" in bootstrap
extensions = load("additional-extensions.json")
assert [e["id"] for e in extensions["extensions"]] == list(EXPECTED_IDS)
assert load("locked-extensions.json") == {"schemaVersion": 1, "extensions": []}
for ext in EXPECTED_IDS:
    pkg = load(f"extensions/{ext}/package.json")
    assert f"{pkg['publisher']}.{pkg['name']}" == ext
    assert pkg.get("browser") and not pkg.get("enabledApiProposals")
manifest = load("demo-provenance.json")
assert manifest["kind"] == "derived-COSW-demo-not-canonical-release"
assert manifest["networkExtraOrigins"] == [GITHUB_ORIGIN]
assert (site / ".nojekyll").exists()
print("demo artifact policy audit: ok")
