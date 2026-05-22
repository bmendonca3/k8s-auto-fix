import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import check_metrics_consistency as checker


class MetricsConsistencyTests(unittest.TestCase):
    def test_check_reports_current_metric_fragments_missing(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "data/outputs/batch_runs/grok_5k").mkdir(parents=True)
            (root / "data/eval").mkdir(parents=True)
            (root / "data").mkdir(exist_ok=True)
            (root / "docs").mkdir(exist_ok=True)
            (root / "paper/overleaf/paper").mkdir(parents=True)
            (root / "data/metrics_rules_full.json").write_text(
                json.dumps(
                    {
                        "detections": 15718,
                        "patches": 13373,
                        "accepted": 13338,
                        "auto_fix_rate": 0.8486,
                        "median_patch_ops": 9,
                    }
                ),
                encoding="utf-8",
            )
            (root / "data/outputs/batch_runs/grok_5k/metrics_grok5k.json").write_text(
                json.dumps({"detections": 5000, "accepted": 4426, "median_patch_ops": 9}),
                encoding="utf-8",
            )
            for relative in [
                "README.md",
                "docs/ablation_rules_vs_grok.md",
                "paper/access.tex",
                "paper/cover_letter.md",
                "paper/overleaf/paper/access.tex",
                "paper/overleaf/paper/cover_letter.md",
            ]:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("stale 13{,}589 / 13{,}656 and 4{,}439 / 5{,}000\n", encoding="utf-8")
            (root / "data/eval/table4_counts.csv").write_text(
                "corpus,accepted,total\n"
                "manifest_slice_rules,13589,13656\n"
                "grok5k_llm,4439,5000\n",
                encoding="utf-8",
            )
            (root / "data/eval/table4_with_ci.csv").write_text(
                "corpus,accepted,total,acceptance_rate,ci_lower,ci_upper\n"
                "manifest_slice_rules,13589,13656,0.9950937316930287,0.9937744854546379,0.9961345044124188\n"
                "grok5k_llm,4439,5000,0.8878,0.8787,0.8963\n",
                encoding="utf-8",
            )
            (root / "data/eval/significance_tests.json").write_text(
                json.dumps(
                    {
                        "acceptance": [
                            {
                                "corpus_a": "supported_rules",
                                "corpus_b": "grok5k_llm",
                                "rate_a": 1.0,
                                "rate_b": 0.8878,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(checker, "ROOT", root):
                failures = checker.check()

        self.assertTrue(any("stale" in failure for failure in failures))
        self.assertTrue(any("current rules" in failure for failure in failures))
        self.assertTrue(any("full_corpus_rules" in failure for failure in failures))
        self.assertTrue(any("significance_tests.json" in failure for failure in failures))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
