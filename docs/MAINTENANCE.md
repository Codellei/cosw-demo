# Unattended release maintenance

Goal: no specific maintainer is needed for **routine compatible release upgrades**.
Failures must not overwrite the previously deployed GitHub Pages demo.

## Release selection

After each successful COSW or Remotish release, GitHub Actions dispatches this maintenance workflow using a short-lived GitHub App token. A daily reconciliation run checks for newer **immutable** releases of
`Codellei/code-oss-static-web` and `Codellei/remotish`. The selector
accepts COSW `v1.*-web.*` and Remotish `v0.1.*-beta.*` only, requiring
published SHA-256 digests and complete assets. The host and GitHub provider
VSIXs must belong to the same Remotish release. Unsupported versions, mutable
releases, missing digests and unknown formats are skipped.

One dedicated bot PR changes **only** `config/releases.lock.json`. It is
refreshed if a newer eligible release appears before merging.

## Reusable release dispatcher

`.github/workflows/notify-release.yml` is stored here and **called by**
the COSW and Remotish release workflows, pinned to an exact commit SHA.

The caller supplies `RELEASE_APP_CLIENT_ID` and
`RELEASE_APP_PRIVATE_KEY` from organization Actions variables/secrets.
The GitHub App must be installed on **only** `cosw-demo`, with
**Actions: read and write** repository permission. The reusable workflow
requests only a `cosw-demo` Actions-write installation token and revokes
it automatically after the job. It does not use a person's PAT.

This dispatch is only a *signal*: the demo independently looks up published,
immutable releases and checks exact SHA-256 asset digests. Calls on ordinary
source branch changes and untrusted pull requests are not used.

Onboarding order: merge and qualify the dispatcher in `cosw-demo` before
enabling upstream reusable workflow callers, or caller dispatches will fail
until the target `release-maintenance.yml` is present on the default branch.
Use daily reconciliation as a fallback for missed notifications.

## One-time configuration

1. Enable **Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests**. Organization policy may also need to allow this. The bot never self-approves, but GitHub requires this setting for its pull-request creation action. The `GITHUB_TOKEN` uses explicitly scoped permissions, not a permanently stored PAT.
2. Keep `master` protected with a required `qualify` check; restrict
   force pushes and unauthorized changes to workflows, code and policy.
3. A required human PR approval cannot coexist with **zero-human**
   lock-update merges unless you configure a narrowly scoped automation
   exception. Do not grant administrator bypass to the workflow.
4. To opt in to unattended merging, create the Actions repository variable
   `AUTO_PROMOTE_ENABLED=true` under **Settings → Secrets and variables →
   Actions → Variables**. The default is *off*: the bot only opens and
   qualifies release-update PRs.

No PAT, long-lived secret or external updater installation is needed.

## Promotion

The bot uses an explicit GitHub Actions `workflow_dispatch` for `pages.yml`
on the exact update branch. GitHub can require human workflow approval for PR
events created by `GITHUB_TOKEN`; explicit dispatch avoids this routine
approval step.

After qualification, the next maintenance run verifies the PR's bot author,
head SHA, branch, base and **lock-only diff**, and confirms that the latest
explicit qualification for its exact head SHA succeeded. Only then, with the
opt-in variable enabled, does it squash-merge without admin bypass. Since bot
merges do not trigger ordinary push workflows, it explicitly dispatches
`pages.yml` on `master`. That workflow reassembles, audits and browser-tests
the entire updated demo before Pages deployment.

If CI fails, the PR is tampered with, GitHub denies merge, or a new release is
incompatible, the automation stops. The old published site remains in place
and the failing workflow/PR is visible to collaborators.

## Limits

This is **low-maintenance**, not a guarantee of zero human intervention in
all circumstances. Upstream major/channel changes, security incidents,
GitHub Pages outages, failing integration tests, and branch-rule changes
require operator judgment. Maintain more than one organization administrator.

Manual smoke: `python3 -m unittest discover -s tests -v`.
To stop automatic merges, set `AUTO_PROMOTE_ENABLED=false`.
