import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_configs.py"
SPEC = importlib.util.spec_from_file_location("validate_configs", MODULE_PATH)
assert SPEC is not None
validate_configs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_configs)


class ValidateConfigsTests(unittest.TestCase):
    def test_checked_in_configs_are_valid(self) -> None:
        paths = validate_configs.default_config_paths()
        results = validate_configs.validate_paths(paths)
        issues = {
            path.relative_to(ROOT).as_posix(): path_issues
            for path, path_issues in results.items()
            if path_issues
        }

        self.assertTrue(paths, "expected checked-in YAML configs")
        self.assertEqual({}, issues)

    def test_invalid_temp_proposer_config_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_config = Path(tmpdir) / "run_bad.yaml"
            invalid_config.write_text(
                "\n".join(
                    [
                        "max_attempts: 0",
                        "proposer:",
                        "  mode: grok",
                        "grok:",
                        "  endpoint: https://example.invalid/v1/chat/completions",
                        "  model: demo-model",
                    ]
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = validate_configs.main([str(invalid_config)])

        self.assertEqual(1, exit_code)
        report = output.getvalue()
        self.assertIn("FAIL", report)
        self.assertIn("max_attempts must be a positive integer", report)
        self.assertIn("grok backend missing non-empty keys: api_key_env", report)

    def test_invalid_retry_budgets_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_config = Path(tmpdir) / "run_bad_retry.yaml"
            invalid_config.write_text(
                "\n".join(
                    [
                        "max_attempts: 3",
                        "retry_budgets:",
                        "  default: 0",
                        "proposer:",
                        "  mode: rules",
                        "  retry_budgets:",
                        "    no_latest_tag: false",
                        "rules:",
                        "  enabled: true",
                    ]
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = validate_configs.main([str(invalid_config)])

        self.assertEqual(1, exit_code)
        report = output.getvalue()
        self.assertIn("retry_budgets.default must be a positive integer", report)
        self.assertIn("proposer.retry_budgets.no_latest_tag must be a positive integer", report)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
