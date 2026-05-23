import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import render_patch_diff


POD_MANIFEST = """\
apiVersion: v1
kind: Pod
metadata:
  name: demo
spec:
  containers:
  - name: web
    image: nginx:latest
"""


CONFIG_MAP_MANIFEST = """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: settings
data:
  mode: unsafe
"""


class RenderPatchDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        base = Path(self.tmpdir.name)
        self.detections_path = base / "detections.json"
        self.patches_path = base / "patches.json"
        detections = [
            {
                "id": "001",
                "manifest_yaml": POD_MANIFEST,
                "policy_id": "no_latest_tag",
                "violation_text": "image uses latest",
            },
            {
                "id": "002",
                "manifest_yaml": CONFIG_MAP_MANIFEST,
                "policy_id": "config_mode",
                "violation_text": "mode is unsafe",
            },
        ]
        self.detections_path.write_text(json.dumps(detections, indent=2), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _write_patches(self, records: list[dict]) -> None:
        self.patches_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def test_main_prints_unified_yaml_diff_for_patch_record(self) -> None:
        self._write_patches(
            [
                {
                    "id": "001",
                    "policy_id": "no_latest_tag",
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/spec/containers/0/image",
                            "value": "nginx:stable",
                        }
                    ],
                }
            ]
        )
        stdout = io.StringIO()

        exit_code = render_patch_diff.main(
            [
                "--detections",
                str(self.detections_path),
                "--patches",
                str(self.patches_path),
            ],
            stdout=stdout,
        )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("--- 001-no_latest_tag:before.yaml", output)
        self.assertIn("+++ 001-no_latest_tag:after.yaml", output)
        self.assertIn("-    image: nginx:latest", output)
        self.assertIn("+    image: nginx:stable", output)

    def test_id_filter_and_accepted_flag_skip_unaccepted_records(self) -> None:
        self._write_patches(
            [
                {
                    "id": "001",
                    "policy_id": "no_latest_tag",
                    "accepted": False,
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/spec/containers/0/image",
                            "value": "nginx:stable",
                        }
                    ],
                },
                {
                    "id": "002",
                    "policy_id": "config_mode",
                    "accepted": True,
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/data/mode",
                            "value": "safe",
                        }
                    ],
                },
            ]
        )
        stdout = io.StringIO()

        render_patch_diff.main(
            [
                "--detections",
                str(self.detections_path),
                "--patches",
                str(self.patches_path),
                "--id",
                "001",
                "--id",
                "002",
            ],
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertNotIn("001-no_latest_tag", output)
        self.assertIn("002-config_mode", output)
        self.assertIn("-  mode: unsafe", output)
        self.assertIn("+  mode: safe", output)

    def test_verified_style_record_can_diff_patched_yaml(self) -> None:
        self._write_patches(
            [
                {
                    "id": "002",
                    "policy_id": "config_mode",
                    "accepted": True,
                    "patched_yaml": CONFIG_MAP_MANIFEST.replace("mode: unsafe", "mode: safe"),
                }
            ]
        )

        diffs = render_patch_diff.render_patch_diffs(self.detections_path, self.patches_path)

        self.assertEqual(len(diffs), 1)
        self.assertIn("-  mode: unsafe", diffs[0])
        self.assertIn("+  mode: safe", diffs[0])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
