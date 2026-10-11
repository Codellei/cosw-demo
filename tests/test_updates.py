"""Tests for fail-closed, immutable-release-only update selection."""
import copy
import json
import unittest

from scripts.build import LOCK_PATH
from scripts.update_releases import (
    asset_digest, eligible_release, release_version, updated_lock,
    UpdateError,
)


def fake_asset(name, digit="a", size=1000):
    return {
        "name": name, "state": "uploaded", "size": size,
        "digest": "sha256:" + digit * 64,
    }


def cosw(tag="v1.141.0-web.3", immutable=True):
    return {
        "tag_name": tag, "immutable": immutable, "draft": False,
        "published_at": "2026-10-12T01:00:00Z",
        "assets": [fake_asset(f"code-oss-static-web-{tag[1:]}.tar.gz")],
    }


def remotish(tag="v0.1.0-beta.16", immutable=True):
    return {
        "tag_name": tag, "immutable": immutable, "draft": False,
        "published_at": "2026-10-12T01:00:00Z",
        "assets": [fake_asset("remotish.vsix"), fake_asset("remotish-github-provider.vsix", "b"),
                   fake_asset("remotish-fixture-provider.vsix", "c")],
    }


class ReleaseUpdateTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads(LOCK_PATH.read_text())

    def test_no_eligible_release_no_change(self):
        self.assertEqual(updated_lock(self.lock, [cosw(immutable=False)],
                                      [remotish(immutable=False)]), self.lock)

    def test_newer_immutable_releases_upgrade_both_entries(self):
        changed = updated_lock(self.lock, [cosw()], [remotish()])
        self.assertEqual(changed["cosw"]["tag"], "v1.141.0-web.3")
        self.assertEqual({x["tag"] for x in changed["extensions"]}, {"v0.1.0-beta.16"})
        self.assertEqual(changed["extensions"][0]["sha256"], "a" * 64)
        self.assertEqual(changed["extensions"][1]["sha256"], "b" * 64)
        self.assertEqual(changed["extensions"][2]["sha256"], "c" * 64)

    def test_monotonic_across_cosw_versions(self):
        changed = updated_lock(self.lock, [cosw("v1.142.0-web.0"), cosw()], [])
        self.assertEqual(changed["cosw"]["tag"], "v1.142.0-web.0")

    def test_missing_asset_digest_and_nonimmutable_skipped(self):
        for asset_index, name in ((1, "remotish-github-provider.vsix"),
                                  (2, "remotish-fixture-provider.vsix")):
            entry = remotish()
            entry["assets"][asset_index].pop("digest")
            self.assertEqual(updated_lock(self.lock, [], [entry])["extensions"],
                             self.lock["extensions"])
            self.assertIsNone(asset_digest(entry, name))
        self.assertIsNone(eligible_release(cosw(immutable=False), "cosw"))

    def test_unknown_channels_require_human_compatibility_review(self):
        self.assertIsNone(release_version("v2.0.0-web.0", "cosw"))
        self.assertIsNone(release_version("v0.2.0-beta.1", "remotish"))
        self.assertIsNone(release_version("v0.1.0", "remotish"))

    def test_malformed_release_refused(self):
        duplicate = cosw()
        duplicate["assets"].append(fake_asset(duplicate["assets"][0]["name"], "b"))
        self.assertEqual(updated_lock(self.lock, [duplicate], []), self.lock)
        bad = cosw()
        bad["assets"][0]["size"] = 900000000
        self.assertEqual(updated_lock(self.lock, [bad], []), self.lock)

    def test_not_downgrading(self):
        self.assertEqual(updated_lock(self.lock, [cosw("v1.141.0-web.1")],
                                      [remotish("v0.1.0-beta.14")]), self.lock)


if __name__ == "__main__":
    unittest.main()
