import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import clean_generated


def write_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class CleanGeneratedPureTests(unittest.TestCase):
    def test_safety_reason_allows_known_generated_outputs(self) -> None:
        allowed = {
            "tmp/run.json": "safe generated prefix tmp/",
            "pkg/__pycache__/module.pyc": "Python bytecode cache",
            ".pytest_cache/v/cache/nodeids": "safe generated prefix .pytest_cache/",
            ".coverage": "coverage output",
            "htmlcov/index.html": "safe generated prefix htmlcov/",
            "build/lib/pkg.py": "safe generated prefix build/",
            "dist/pkg.whl": "safe generated prefix dist/",
            "src/pkg.egg-info/PKG-INFO": "Python egg-info metadata",
        }

        for path, expected_reason in allowed.items():
            with self.subTest(path=path):
                self.assertEqual(expected_reason, clean_generated.safety_reason(path))

    def test_safety_reason_rejects_unsafe_or_broad_paths(self) -> None:
        rejected = (
            "",
            ".",
            "/",
            "../tmp/out",
            " tmp/out",
            "data/generated/out.json",
            ".venv/bin/python",
            "logs/run.log",
        )

        for path in rejected:
            with self.subTest(path=path):
                self.assertIsNone(clean_generated.safety_reason(path))

    def test_parse_ignored_status_keeps_only_ignored_paths(self) -> None:
        output = b" M README.md\0?? scratch.txt\0!! tmp/out.txt\0!! build/\0"

        self.assertEqual(
            ["tmp/out.txt", "build"],
            clean_generated.parse_ignored_status(output),
        )

    def test_cleanup_candidates_marks_skipped_paths(self) -> None:
        candidates = clean_generated.cleanup_candidates(["tmp/out.txt", ".venv/bin/python"])

        self.assertEqual(
            [
                clean_generated.CleanupCandidate(
                    "tmp/out.txt",
                    True,
                    "safe generated prefix tmp/",
                ),
                clean_generated.CleanupCandidate(
                    ".venv/bin/python",
                    False,
                    "outside safe generated-output allowlist",
                ),
            ],
            candidates,
        )


class CleanGeneratedGitTests(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        subprocess.run(
            ["git", "init"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        write_file(
            root / ".gitignore",
            "\n".join(
                [
                    "tmp/",
                    "__pycache__/",
                    ".pytest_cache/",
                    ".coverage",
                    "htmlcov/",
                    "build/",
                    "dist/",
                    "*.egg-info/",
                    ".venv/",
                ]
            )
            + "\n",
        )
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return temp_dir

    def test_main_defaults_to_list_mode_without_deleting(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            write_file(root / "tmp" / "out.txt", "generated")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = clean_generated.main(["--repo-root", str(root)])

            self.assertEqual(0, result)
            self.assertEqual(["tmp"], stdout.getvalue().splitlines())
            self.assertTrue((root / "tmp" / "out.txt").exists())

    def test_discover_candidates_lists_only_ignored_safe_outputs_as_safe(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            write_file(root / "tmp" / "out.txt", "generated")
            write_file(root / "htmlcov" / "index.html", "coverage")
            write_file(root / ".venv" / "bin" / "python", "local env")

            candidates = clean_generated.discover_candidates(root)
            by_path = {candidate.path: candidate for candidate in candidates}

            self.assertTrue(by_path["tmp"].safe)
            self.assertTrue(by_path["htmlcov"].safe)
            self.assertFalse(by_path[".venv"].safe)

    def test_delete_candidate_removes_safe_ignored_path_only_after_git_checks(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            write_file(root / "tmp" / "out.txt", "generated")
            candidate = clean_generated.CleanupCandidate(
                "tmp",
                True,
                "safe generated prefix tmp/",
            )

            clean_generated.delete_candidate(root, candidate)

            self.assertFalse((root / "tmp").exists())

    def test_delete_candidate_refuses_tracked_files_under_safe_prefix(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            write_file(root / "tmp" / "keep.txt", "tracked")
            subprocess.run(
                ["git", "add", "-f", "tmp/keep.txt"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            candidate = clean_generated.CleanupCandidate(
                "tmp",
                True,
                "safe generated prefix tmp/",
            )

            with self.assertRaisesRegex(clean_generated.CleanupRefused, "tracked entries"):
                clean_generated.delete_candidate(root, candidate)

            self.assertTrue((root / "tmp" / "keep.txt").exists())

    def test_delete_candidate_refuses_paths_outside_safe_allowlist(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            write_file(root / ".venv" / "bin" / "python", "local env")
            candidate = clean_generated.CleanupCandidate(
                ".venv",
                False,
                "outside safe generated-output allowlist",
            )

            with self.assertRaisesRegex(clean_generated.CleanupRefused, "outside safe"):
                clean_generated.delete_candidate(root, candidate)

            self.assertTrue((root / ".venv" / "bin" / "python").exists())

    def test_delete_candidate_refuses_broad_roots_even_if_marked_safe(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            candidate = clean_generated.CleanupCandidate(".", True, "bad input")

            with self.assertRaisesRegex(clean_generated.CleanupRefused, "outside safe"):
                clean_generated.delete_candidate(root, candidate)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
