import json
import tempfile
import unittest
from pathlib import Path

from src.eval.metrics import run as metrics_run


class MetricsTests(unittest.TestCase):
    def test_metrics_reports_failure_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            detections_path = tmp_path / "detections.json"
            patches_path = tmp_path / "patches.json"
            verified_path = tmp_path / "verified.json"
            out_path = tmp_path / "metrics.json"

            detections = [
                {"id": "001"},
                {"id": "002"},
                {"id": "003"},
            ]
            patches = [
                {"id": "001", "patch": [{"op": "add", "path": "/metadata/labels/env", "value": "prod"}]},
                {"id": "002", "patch": [{"op": "remove", "path": "/spec/containers/0/securityContext/privileged"}]},
                {"id": "003", "patch": []},
            ]
            verified = [
                {"id": "001", "accepted": True, "ok_schema": True, "ok_policy": True, "ok_safety": True, "ok_rescan": True},
                {"id": "002", "accepted": False, "ok_schema": True, "ok_policy": False, "ok_safety": False, "ok_rescan": True},
                {"id": "003", "accepted": False, "ok_schema": False, "ok_policy": True, "ok_safety": True, "ok_rescan": False},
            ]

            detections_path.write_text(json.dumps(detections, indent=2), encoding="utf-8")
            patches_path.write_text(json.dumps(patches, indent=2), encoding="utf-8")
            verified_path.write_text(json.dumps(verified, indent=2), encoding="utf-8")

            metrics_run(
                detections=detections_path,
                patches=patches_path,
                verified=verified_path,
                out=out_path,
            )

            metrics = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["detections"], 3)
            self.assertEqual(metrics["accepted"], 1)
            self.assertEqual(metrics["median_patch_ops"], 1)
            self.assertEqual(metrics["failed_policy"], 1)
            self.assertEqual(metrics["failed_schema"], 1)
            self.assertEqual(metrics["failed_safety"], 1)
            self.assertEqual(metrics["failed_rescan"], 1)
            self.assertAlmostEqual(metrics["auto_fix_rate"], round(1 / 3, 4))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
