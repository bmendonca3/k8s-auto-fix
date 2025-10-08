import json
import unittest
from pathlib import Path

import jsonpatch
import yaml


class PatchMinimalityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patches_path = Path("data/patches.json")
        self.detections_path = Path("data/detections.json")
        if not self.patches_path.exists() or not self.detections_path.exists():
            self.skipTest("patch dataset not available; run proposer to generate patches.json")
        self.patches = json.loads(self.patches_path.read_text())
        raw_detections = json.loads(self.detections_path.read_text())
        self.detections = {
            str(entry.get("id")): entry for entry in raw_detections if isinstance(entry, dict)
        }

    def test_patch_is_list_and_small(self) -> None:
        for record in self.patches:
            self.assertIsInstance(record.get("patch"), list)
            self.assertLessEqual(len(record["patch"]), 6)

    def test_idempotent_apply(self) -> None:
        for record in self.patches:
            detection = self.detections.get(str(record.get("id")))
            if not detection:
                continue
            manifest_yaml = detection.get("manifest_yaml")
            if manifest_yaml is None:
                manifest_path = detection.get("manifest_path")
                if manifest_path:
                    path_obj = Path(manifest_path)
                    if not path_obj.is_absolute():
                        path_obj = self.detections_path.parent / path_obj
                    manifest_yaml = path_obj.read_text()
            if manifest_yaml is None:
                continue
            base_obj = yaml.safe_load(manifest_yaml)
            once = jsonpatch.apply_patch(base_obj, record["patch"], in_place=False)
            second_base = yaml.safe_load(manifest_yaml)
            twice = jsonpatch.apply_patch(second_base, record["patch"], in_place=False)
            self.assertEqual(yaml.safe_dump(once), yaml.safe_dump(twice))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
