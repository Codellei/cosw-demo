"""Fail-closed checks for the reusable GitHub App dispatcher."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseDispatcherTests(unittest.TestCase):
    def test_dispatcher_is_restricted_to_approved_upstream_repos(self):
        workflow = (ROOT / ".github/workflows/notify-release.yml").read_text()
        self.assertIn("workflow_call:", workflow)
        self.assertIn("github.ref_type == 'tag'", workflow)
        self.assertIn("github.repository == 'Codellei/remotish'", workflow)
        self.assertIn("github.repository == 'Codellei/code-oss-static-web'", workflow)
        self.assertIn("repositories: cosw-demo", workflow)
        self.assertIn("permission-actions: write", workflow)
        self.assertNotIn("permission-contents: write", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertIn("gh workflow run release-maintenance.yml", workflow)
        self.assertIn("--ref master", workflow)
        self.assertRegex(workflow, r"uses: actions/create-github-app-token@[0-9a-f]{40}")

    def test_reconciliation_and_head_sha_gate(self):
        workflow = (ROOT / ".github/workflows/release-maintenance.yml").read_text()
        self.assertIn('cron: "17 7 * * *"', workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("github.ref == 'refs/heads/master'", workflow)
        self.assertIn("AUTO_PROMOTE_ENABLED", workflow)
        shell = (ROOT / "scripts/maintain.sh").read_text()
        self.assertIn("--match-head-commit", shell)
        self.assertIn('[[ "$changed" == "$FILE" ]]', shell)
        self.assertIn("gh workflow run pages.yml", shell)
        self.assertIn('AUTO_PROMOTE_ENABLED:-', shell)
        self.assertNotIn("gh pr merge --admin", shell)


if __name__ == "__main__":
    unittest.main()
