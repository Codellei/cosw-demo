# Architecture and security contract

## Scope and threat model

COSW Demo is a **static, anonymous, public, read-only** integration example. The GitHub provider can load public repositories via `https://api.github.com`. No backend, shared GitHub token, authentication flow, service worker or server-side proxy exists. It deliberately does **not** provide private repository access or authenticated commits/pushes.

## Pinned supply chain

The lock file records one exact COSW `.tar.gz` and two exact Remotish browser VSIXs. Every URL must reference an explicit Codellei GitHub Release tag and is verified against a pinned SHA-256. Downloads are size bounded and redirects restricted to GitHub release asset hosts over HTTPS. The assembler rejects archive traversal, symlinks, duplicate paths, nonregular files, zip bombs, mismatched extension IDs/versions, unapproved licenses, missing browser entrypoints, unexpected extension dependencies and proposed API grants.

SHA-256 verification establishes consistency with the reviewed pinned bytes, but is not by itself a cryptographic identity proof for a publisher. Review source, release provenance, attestations, licenses, browser compatibility and the exact digest when updating the lock.

## Derived COSW policy

COSW `v1.141.0-web.2` supplies the native workspace provider and preserves browser-owned local folders. The upstream COSW release is immutable; this repository only prepares an independently tested derivative of those bytes for GitHub Pages. A strict COSW bootstrap/CSP shape check allows exactly:

- Extra built-in browser extensions `hrashton.remotish` and `hrashton.remotish-github-provider`, from SHA-verified VSIXs. Canonical COSW `locked-extensions.json` remains empty and unchanged.
- Built-in `Default Dark+` theme and an empty first-visit workspace. A validated GitHub deep link can open a public repository, and existing workspace persistence remains available.
- One additional `connect-src` origin, `https://api.github.com`. No wildcard, external script origin, `unsafe-eval`, proposed API, telemetry or webview enablement.

The generated `demo-provenance.json` records the source commit, upstream checksums, installed extensions and policy change. It is a **derived-artifact manifest**, not a claim that COSW's release attestation covers the derivative.

## Qualification and promotion

Read-only pull requests run fixture-based adversarial unit tests, SHA-pinned assembly, a policy audit, and headless Chromium qualification. The browser test must boot Code OSS, configure the dark theme, register both extensions and receive a successful public repository request through the GitHub provider. Only protected `master` workflows can upload one Pages artifact and deploy using Pages/OIDC job permissions.

Repository administrators must select GitHub Actions as Pages source, protect `master`, require review and checks, and optionally require approval for the `github-pages` environment. Do not deploy artifacts built by untrusted PRs. All runtime code and data is static and works from a GitHub Pages project subpath.

## Public users and limitations

Anonymous GitHub API requests are rate limited, may be blocked by network policies, and reveal normal request metadata such as IP address to GitHub. Browser CORS/COEP interactions may change. Third-party installed extensions are not reviewed or supported by this demo.

GitHub Pages does not supply arbitrary custom HTTP security headers; the demo retains COSW's CSP meta tag. Its test tuple is a Playwright-managed Chromium browser on the CI runner, not an enterprise browser support promise. Changes to OAuth, write access, origins, supported browsers or extension intake require new threat modeling and qualification.
