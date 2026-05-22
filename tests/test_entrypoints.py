import importlib
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None


EXPECTED_SCRIPTS = {
    "k8s-auto-fix-detect": "src.detector.cli:app",
    "k8s-auto-fix-propose": "src.proposer.cli:app",
    "k8s-auto-fix-verify": "src.verifier.cli:app",
    "k8s-auto-fix-schedule": "src.scheduler.cli:app",
    "k8s-auto-fix-queue": "src.scheduler.queue_cli:app",
}

CONSOLE_SCRIPT_HELP_TOKENS = {
    "k8s-auto-fix-detect": ("--in", "--policies-dir"),
    "k8s-auto-fix-propose": ("--detections", "--metrics-out", "--cache-dir"),
    "k8s-auto-fix-verify": ("--patches", "--gate-profile"),
    "k8s-auto-fix-schedule": ("--verified", "--batch-group-by"),
    "k8s-auto-fix-queue": ("Persistent risk-aware patch queue", "enqueue"),
}

SCRIPT_HELP_TOKENS = {
    "scripts/run_grok43_benchmark.py": ("Grok 4.3 benchmark", "--run-id", "--kube-linter-cmd"),
    "scripts/run_pipeline.py": ("--dry-run", "--manifest-out", "--status-out"),
    "scripts/run_tiny_regression.py": ("tiny Kubernetes auto-fix regression", "--json"),
    "scripts/validate_configs.py": ("Validate checked-in YAML config", "paths"),
    "scripts/check_docs_links.py": ("Check local links", "paths"),
    "scripts/check_metrics_consistency.py": ("paper-facing metric text", "--json"),
    "scripts/scan_secrets.py": ("Scan tracked", "--include-artifacts"),
    "scripts/clean_generated.py": ("ignored generated outputs", "--delete"),
    "scripts/artifact_index.py": ("Index tracked artifact-like files", "--limit"),
    "scripts/artifact_traceability.py": ("Report artifact size", "--producer"),
    "scripts/build_evidence_manifest.py": (
        "evidence manifest",
        "--claim",
        "--claims-table",
        "--pipeline-manifest",
    ),
    "scripts/render_patch_diff.py": ("unified before/after YAML diffs", "--id"),
    "scripts/verifier_report.py": ("concise failure report", "--max-groups"),
    "scripts/scheduler_explain.py": ("scheduler prioritisation", "--json"),
    "scripts/queue_report.py": ("Report scheduler queue health", "--top"),
    "scripts/build_review_packet.py": ("operator review packet", "--max-diffs", "--batches"),
    "scripts/gitops_writeback.py": ("Apply accepted patches", "--dry-run", "--plan-out"),
}


@unittest.skipIf(tomllib is None, "tomllib is not available on this Python version")
class EntryPointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.project_root = project_root
        with (project_root / "pyproject.toml").open("rb") as handle:
            cls.pyproject = tomllib.load(handle)

    def test_pyproject_console_scripts_match_expected_targets(self) -> None:
        scripts = self.pyproject.get("project", {}).get("scripts", {})

        self.assertEqual(scripts, EXPECTED_SCRIPTS)

    def test_declared_python_floor_matches_ci_matrix(self) -> None:
        project = self.pyproject.get("project", {})

        self.assertEqual(">=3.10", project.get("requires-python"))

    def test_console_script_targets_expose_callable_typer_apps(self) -> None:
        import typer

        scripts = self.pyproject.get("project", {}).get("scripts", {})

        for script_name, target in scripts.items():
            with self.subTest(script=script_name):
                module_name, separator, attribute_name = target.partition(":")
                self.assertEqual(separator, ":", f"{target!r} must use 'module:attribute' syntax")
                self.assertTrue(module_name, f"{target!r} is missing a module name")
                self.assertTrue(attribute_name, f"{target!r} is missing an attribute name")

                module = importlib.import_module(module_name)
                app = getattr(module, attribute_name)

                self.assertIsInstance(app, typer.Typer)
                self.assertTrue(callable(app))

    def test_console_script_modules_show_help(self) -> None:
        scripts = self.pyproject.get("project", {}).get("scripts", {})

        for script_name, expected_tokens in CONSOLE_SCRIPT_HELP_TOKENS.items():
            with self.subTest(script=script_name):
                target = scripts[script_name]
                module_name, _, _ = target.partition(":")
                completed = self._run_help([sys.executable, "-m", module_name, "--help"])
                output = completed.stdout + completed.stderr

                self.assertIn("Usage", output)
                for token in expected_tokens:
                    self.assertIn(token, output)

    def test_installed_console_scripts_show_help(self) -> None:
        scripts = self.pyproject.get("project", {}).get("scripts", {})

        for script_name, expected_tokens in CONSOLE_SCRIPT_HELP_TOKENS.items():
            with self.subTest(script=script_name):
                script_path = self._installed_script_path(script_name)
                if script_path is None:
                    self.skipTest(f"{script_name} is not installed")

                completed = self._run_help([script_path, "--help"])
                output = completed.stdout + completed.stderr

                self.assertIn("Usage", output)
                for token in expected_tokens:
                    self.assertIn(token, output)

    def test_documented_helper_scripts_show_help(self) -> None:
        for script_path, expected_tokens in SCRIPT_HELP_TOKENS.items():
            with self.subTest(script=script_path):
                completed = self._run_help([sys.executable, script_path, "--help"])
                output = completed.stdout + completed.stderr

                self.assertIn("usage:", output.lower())
                for token in expected_tokens:
                    self.assertIn(token, output)

    @classmethod
    def _run_help(cls, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=cls.project_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )

    @staticmethod
    def _installed_script_path(script_name: str) -> Optional[str]:
        path_script = shutil.which(script_name)
        if path_script is not None:
            return path_script

        interpreter_script = Path(sys.executable).parent / script_name
        if interpreter_script.exists():
            return str(interpreter_script)

        return None


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
