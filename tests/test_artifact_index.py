import csv
import io
import subprocess
import unittest

from scripts import artifact_index


class ArtifactIndexTests(unittest.TestCase):
    def test_category_for_classifies_supported_artifacts(self) -> None:
        cases = {
            ".DS_Store": "local-metadata",
            "data/corpora/pod.yaml": "data-input",
            "data/eval/results.json": "generated-output",
            "data/cache.sqlite3": "runtime-state",
            "data/misc/blob.bin": "data-artifact",
            "paper/figures/chart.PNG": "figure",
            "paper/build/output.pdf": "paper-output",
            "paper/archives/source.zip": "archive",
            "logs/run.txt": "log",
            "verification/latest.json": "log",
            "service.out": "log",
            "archives/bundle.tar.gz": "archive",
            "figures/overview.svg": "figure",
            "state.db": "runtime-state",
            "release.pkg": "binary-package",
        }

        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(expected, artifact_index.category_for(path))

    def test_category_for_ignores_documentation_and_source_files(self) -> None:
        for path in ("data/README.md", "archives/README.md", "src/app.py"):
            with self.subTest(path=path):
                self.assertIsNone(artifact_index.category_for(path))

    def test_subprocess_stderr_normalizes_none_bytes_and_text(self) -> None:
        cases = [
            (subprocess.CalledProcessError(1, ["git"], stderr=None), ""),
            (subprocess.CalledProcessError(1, ["git"], stderr=b"fatal: nope\n"), "fatal: nope\n"),
            (subprocess.CalledProcessError(1, ["git"], stderr="plain text"), "plain text"),
        ]

        for exc, expected in cases:
            with self.subTest(stderr=exc.stderr):
                self.assertEqual(expected, artifact_index.subprocess_stderr(exc))

    def test_write_csv_outputs_artifact_rows(self) -> None:
        artifacts = [
            artifact_index.Artifact(
                path="data/corpora/pod.yaml",
                category="data-input",
                kind="file",
                size_bytes=17,
                sha256="a" * 64,
            ),
            artifact_index.Artifact(
                path="logs/run,latest.log",
                category="log",
                kind="symlink",
                size_bytes=8,
                sha256="b" * 64,
            ),
        ]
        handle = io.StringIO()

        artifact_index.write_csv(artifacts, handle)

        output = handle.getvalue()
        self.assertTrue(output.startswith("path,category,kind,size_bytes,sha256\n"))
        rows = list(csv.DictReader(io.StringIO(output)))
        self.assertEqual(
            [
                {
                    "path": "data/corpora/pod.yaml",
                    "category": "data-input",
                    "kind": "file",
                    "size_bytes": "17",
                    "sha256": "a" * 64,
                },
                {
                    "path": "logs/run,latest.log",
                    "category": "log",
                    "kind": "symlink",
                    "size_bytes": "8",
                    "sha256": "b" * 64,
                },
            ],
            rows,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
