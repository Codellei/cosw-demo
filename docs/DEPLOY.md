# Deploy your own Remotish demo

This repository builds **one** pinned COSW + Dark+ + Remotish + GitHub Provider
configuration for a public, read-only GitHub Pages website. No server or token
is necessary for anonymous public repository browsing.

1. Fork this repository into your GitHub account or organization.
2. In **Settings → Pages → Build and deployment**, select
   **Source: GitHub Actions**.
3. Protect `master`: require reviews and a successful `qualify` check.
   Restrict force-pushes/bypass and review changes to release pins, workflows
   and the network policy.
4. Merge the reviewed code to `master`, or run **Qualify and deploy demo**
   from the Actions tab. The Pages job runs only after the offline security
   checks, artifact audit and live Chromium GitHub-provider test succeed.
5. Open `https://YOUR-OWNER.github.io/YOUR-REPO/`. The editor and
   extension URLs are relative, so the project subpath is supported.

**Change the README's demo links** to your own Pages URL. For other public
repositories, users can follow `?repo=OWNER/REPOSITORY`.

## Updating the releases

`config/releases.lock.json` is the only source of release input identities.
A scheduled workflow can select newer immutable releases, open a lock-only PR,
qualify the candidate and optionally merge it without a human. See
[unattended maintenance](MAINTENANCE.md) for the one-time opt-in and guardrails.
For manual upgrades, select official immutable release assets and review
compatibility, licenses, published SHA-256 values and provenance before updating.
The build refuses unpinned inputs and unsafe extension packages.
Do not replace an official artifact with a patched copy claiming the
original publisher's attestation.

## Trust and qualification

The PR workflow runs read-only and **does not publish previews**. Only reviewed
`master` builds deploy to the Pages site. Changes to the canonical COSW runtime
remain outside this repository. The demo adds only `https://api.github.com`
to the original network policy, disables host telemetry and webviews, and uses
two pinned browser-compatible VSIX files.

GitHub Pages serves a static site and cannot configure arbitrary HTTP response
security headers. This workflow tests Chromium on GitHub Actions; it is not a
promise about every enterprise browser, proxy or host configuration.
For the full threat model, see [architecture](architecture.md).
