import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.plot_mode_comparison import DISPLAY_LABELS, load_comparison


class ModeComparisonTests(unittest.TestCase):
    def test_released_modes_have_guardrail_labels(self) -> None:
        self.assertEqual(DISPLAY_LABELS["rules+guardrails"], "Rules +\nguards")
        self.assertEqual(DISPLAY_LABELS["grok+rule-guardrails"], "Grok +\nguards")

    def test_accepts_shared_corpus_rows(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "comparison.csv"
            path.write_text(
                "corpus,mode,manifests,accepted,acceptance_rate,source_metrics\n"
                "shared,rules-only,10,9,0.9,rules.json\n"
                "shared,llm-only,10,8,0.8,llm.json\n",
                encoding="utf-8",
            )
            frame = load_comparison(path)
        self.assertEqual(frame["corpus"].nunique(), 1)

    def test_rejects_mixed_denominators(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "comparison.csv"
            path.write_text(
                "corpus,mode,manifests,accepted,acceptance_rate,source_metrics\n"
                "full,rules-only,10,9,0.9,rules.json\n"
                "shared,llm-only,20,16,0.8,llm.json\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "shared corpus"):
                load_comparison(path)

    def test_rejects_inconsistent_rate(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "comparison.csv"
            path.write_text(
                "corpus,mode,manifests,accepted,acceptance_rate,source_metrics\n"
                "shared,rules-only,10,9,0.8,rules.json\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "accepted/manifests"):
                load_comparison(path)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
