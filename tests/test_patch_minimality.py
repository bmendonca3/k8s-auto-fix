import json
import unittest
from pathlib import Path

import jsonpatch
import yaml


class PatchMinimalityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patches_path = Path("data/patches.json")
        self.manifest_path = Path("data/manifests/001.yaml")
        if not self.patches_path.exists() or not self.manifest_path.exists():
            self.skipTest("patch dataset not available; run proposer to generate patches.json")
        self.patches = json.loads(self.patches_path.read_text())
        self.base_yaml = self.manifest_path.read_text()

    def test_patch_is_list_and_small(self) -> None:
        for record in self.patches:
            self.assertIsInstance(record.get("patch"), list)
            self.assertLessEqual(len(record["patch"]), 5)

    def test_idempotent_apply(self) -> None:
        base_obj = yaml.safe_load(self.base_yaml)
        for record in self.patches:
            once = jsonpatch.apply_patch(base_obj, record["patch"], in_place=False)
            twice = jsonpatch.apply_patch(once, record["patch"], in_place=False)
            self.assertEqual(yaml.safe_dump(once), yaml.safe_dump(twice))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
