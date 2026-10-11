# COSW Remotish demo

A **single, static Code OSS Web demo** powered by
[Code OSS Static Web (COSW)](https://github.com/Codellei/code-oss-static-web),
[Remotish](https://github.com/Codellei/remotish), and its GitHub provider.
Includes the built-in **Dark+** theme and Remotish's deterministic fixture provider.

**[Open demo](https://codellei.github.io/cosw-demo/)** ·
[How to use it](docs/USING.md) ·
[Deploy your own](docs/DEPLOY.md)

The demo opens public GitHub repositories **without signing in**.
On a fresh visit, the demo opens an **empty editor**. Select **File → Open Folder** for browser-supported folders, or open a public GitHub repository with:

```text
https://codellei.github.io/cosw-demo/?repo=Codellei/remotish
```

For an offline sample repository, open the **Command Palette** and run
**Remotish Demo: Open Fixture Repository**. The fixture is deterministic and
does not access GitHub.

The GitHub provider uses **anonymous, read-only GitHub access**. You can browse, edit and stage
changes locally in Remotish's browser overlay; **nothing is pushed to GitHub**.
Private repositories, GitHub login, and remote write operations are not supported.
The public Pages link is usable only after a reviewed, qualified deployment.

## What's included

- One SHA-256-pinned COSW `v1.141.0-web.2` release archive.
- Three SHA-256-pinned Remotish `v0.1.0-beta.15` browser VSIXs (host, GitHub provider, fixture provider).
- Dark+ theme, an empty first-visit workspace, fixture demo command, and a validated `?repo=OWNER/REPO` selector.
- An independently identified derived distribution with one extra permitted
  network origin: `https://api.github.com`.
- A read-only PR qualification job; GitHub Pages deployment from `master`
  only after offline tests, policy audit, and a live Chromium GitHub API test pass.

COSW and Remotish release workflows can notify the demo through a reusable, GitHub App-authenticated dispatcher. A daily fallback check and a head-SHA-gated, opt-in promotion process keep compatible immutable-release updates unattended. See [maintenance](docs/MAINTENANCE.md). No backend, shared GitHub token, OAuth flow or third-party hosting is needed.
Host telemetry, proposed API grants and webviews remain disabled.

## Developer quickstart

Requires Python 3.11+:

```sh
python3 -m unittest discover -s tests -v
python3 -m scripts.build
python3 -m scripts.audit _site
python3 -m http.server 8000 --directory _site
```

Open `http://127.0.0.1:8000/`. For the same Chromium check used in CI,
install Node.js 24 and run `npm install --ignore-scripts --package-lock=false`,
`npx playwright install chromium`, then `node tests/browser.mjs`.

The distribution is **a derivative demo**, not an official COSW release or
enterprise-supported deployment. Original upstream attestations do not attest to
the modified output. See the [architecture and security model](docs/architecture.md)
and [security policy](SECURITY.md). No multi-profile catalog or PR-preview
deployment is part of this repository.
