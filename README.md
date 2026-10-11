# COSW demo

A minimal, public, zero-backend [Code OSS Static Web](https://github.com/Codellei/code-oss-static-web) deployment with **Default Dark+**, [Remotish](https://github.com/Codellei/remotish) and the **Remotish GitHub Provider**.

**Demo URL (after successful Pages deployment):** https://codellei.github.io/cosw-demo/

This site opens the **public** `octocat/Hello-World` GitHub repository by default. Visitors need **no GitHub account or token**. This is anonymous, **read-only public-repository access**, not GitHub sign-in, private-repository access, or an authenticated push client.

## Architecture

```text
Exact COSW release tar.gz + two Remotish VSIX releases
     |
     | SHA-256 pin, safe extraction, browser entrypoint and license checks
     v
Python stdlib assembler
     | - register 2 additional browser extensions
     | - Dark+ and a sample public GitHub workspace
     | - add only api.github.com to connect-src
     v
Derived _site/ output + demo-provenance.json
     |
Offline tests -> policy audit -> Chromium live GitHub-provider test
     |
Qualified GitHub Pages artifact -> single Pages deployment
```

The canonical COSW tarball is never changed or re-released. This is a separately qualified **derived demo**, not a supported COSW profile. The extension lock and SHA-256 values in [config/releases.lock.json](config/releases.lock.json) are reviewed and never follow `latest`.

## Local build

Python 3.11+ (standard library only) is required:

```sh
python3 -m unittest discover -s tests -v
python3 -m scripts.build
python3 -m scripts.audit _site
python3 -m http.server 8000 --directory _site
```

Open http://127.0.0.1:8000/. Network access to GitHub Releases is needed for the first build. For full Chromium qualification (Node.js 24):

```sh
npm install --ignore-scripts --package-lock=false
npx playwright install chromium
node tests/browser.mjs
```

The browser test starts its own local server on port 8765 and requires the anonymous GitHub REST API to be reachable.

## Fork to GitHub Pages

1. Fork this repo. Review [the architecture and threat model](docs/architecture.md) and [security policy](SECURITY.md).
2. Under **Settings → Pages → Build and deployment**, set **Source: GitHub Actions**.
3. Protect `master` and require PR review and the `qualify` status check for workflow, policy, and dependency-pin changes.
4. Merge a qualified change or manually dispatch **Qualify and deploy demo** from `master`. A failing build or browser test prevents publication.
5. Open https://OWNER.github.io/REPOSITORY/. All runtime asset URLs remain relative to the project's Pages path.

The PR job has read-only GitHub permissions and cannot deploy untrusted PR content. Pages deployment uses a short-lived GitHub OIDC token scoped to its deploy job. No GitHub tokens, OAuth flow, application secrets, server or proxy are needed.

## Compatibility and limits

Currently pinned COSW `v1.141.0-web.2` includes the Open VSX-ready profile and native workspace persistence / URI restoration added in COSW PRs #110 and #112. Both Remotish VSIXs are pinned at `v0.1.0-beta.15`. Runtime activation is subject to the browser qualification workflow; the public Open VSX registry alone does not establish compatibility. This demo does not change COSW's canonical production extension-lock admission/mirror policy.

The derived CSP permits `https://api.github.com` as the **only** extra connection origin beyond those already present in the pinned COSW release. Proposed APIs, workbench telemetry and webviews remain disabled. GitHub anonymous API limits and CORS restrictions apply, and GitHub can receive visitors' IP addresses through direct browser requests.

Do not use this demonstration with private data or credentials. Playwright Chromium qualification does not imply support for every OS/browser, enterprise proxy, or managed client. See [docs/architecture.md](docs/architecture.md).
