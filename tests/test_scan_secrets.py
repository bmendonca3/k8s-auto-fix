import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import scan_secrets


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class ScanSecretsPureTests(unittest.TestCase):
    def test_scan_text_detects_and_redacts_common_tokens(self) -> None:
        openai_key = "sk-proj-" + ("abc123" * 6)
        client_value = "AbCdEfGhIjKlMnOpQrStUvWxYz123456"
        findings = scan_secrets.scan_text(
            "config.env",
            "\n".join(
                [
                    f'OPENAI_API_KEY="{openai_key}"',
                    f'client_secret="{client_value}"',
                ]
            ),
        )

        self.assertEqual(["openai-api-key", "generic-secret-assignment"], [f.rule for f in findings])
        self.assertIn("sk-p...c123", findings[0].evidence)
        self.assertNotIn("abc123abc123abc123abc123", findings[0].evidence)

    def test_scan_text_skips_doc_placeholders_and_low_entropy_values(self) -> None:
        findings = scan_secrets.scan_text(
            "README.md",
            "\n".join(
                [
                    "Use `OPENAI_API_KEY=\"sk-proj-exampleexampleexampleexampleexample\"`.",
                    'password="aaaaaaaaaaaaaaaaaaaa"',
                    'token="your-token-goes-here"',
                ]
            ),
        )

        self.assertEqual([], findings)

    def test_scan_text_detects_real_tokens_in_doc_code_spans(self) -> None:
        github_token = "ghp_" + ("A1b2C3d4E5f6" * 3)

        findings = scan_secrets.scan_text(
            "docs/setup.md",
            f'Run `export GITHUB_TOKEN="{github_token}"` before publishing.\n',
        )

        self.assertEqual(["github-token"], [finding.rule for finding in findings])
        self.assertIn("ghp_...E5f6", findings[0].evidence)
        self.assertNotIn(github_token, findings[0].evidence)

    def test_private_key_headers_are_not_suppressed_in_docs(self) -> None:
        private_key_header = "-----BEGIN " + "PRIVATE KEY-----"
        findings = scan_secrets.scan_text(
            "docs/security.md",
            private_key_header + "\n",
        )

        self.assertEqual(1, len(findings))
        self.assertEqual("private-key", findings[0].rule)


class ScanSecretsGitTests(unittest.TestCase):
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
        write_file(root / ".gitignore", "tmp/\n*.bin\n")
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return temp_dir

    def test_scan_repo_uses_tracked_and_unignored_files(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            client_value = "AbCdEfGhIjKlMnOpQrStUvWxYz123456"
            aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            ignored_key = "AKIA" + ("Z" * 16)
            write_file(root / "tracked.env", f'api_key="{client_value}"\n')
            write_file(root / "untracked.env", f"AWS_ACCESS_KEY_ID={aws_key}\n")
            write_file(root / "tmp" / "ignored.env", f"AWS_ACCESS_KEY_ID={ignored_key}\n")
            subprocess.run(
                ["git", "add", "tracked.env"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            findings = scan_secrets.scan_repo(root)

            self.assertEqual(
                [("tracked.env", "generic-secret-assignment"), ("untracked.env", "aws-access-key-id")],
                [(finding.path, finding.rule) for finding in findings],
            )

    def test_tracked_only_skips_untracked_files(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            other_key = "AKIA" + ("Z" * 16)
            write_file(root / "tracked.env", f"AWS_ACCESS_KEY_ID={aws_key}\n")
            write_file(root / "untracked.env", f"AWS_ACCESS_KEY_ID={other_key}\n")
            subprocess.run(
                ["git", "add", "tracked.env"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            findings = scan_secrets.scan_repo(root, tracked_only=True)

            self.assertEqual(["tracked.env"], [finding.path for finding in findings])

    def test_cli_returns_nonzero_on_findings(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            write_file(root / "secret.env", f"AWS_ACCESS_KEY_ID={aws_key}\n")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = scan_secrets.main(["--repo-root", str(root)])

            self.assertEqual(1, result)
            self.assertIn("secret.env:1: aws-access-key-id", stdout.getvalue())

    def test_default_scan_skips_artifact_heavy_sample_paths(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            sample_path = root / "data" / "manifests" / "the_stack_sample" / "sample.yaml"
            write_file(sample_path, f"AWS_ACCESS_KEY_ID={aws_key}\n")
            subprocess.run(
                ["git", "add", str(sample_path.relative_to(root))],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual([], scan_secrets.scan_repo(root))
            self.assertEqual(
                ["data/manifests/the_stack_sample/sample.yaml"],
                [finding.path for finding in scan_secrets.scan_repo(root, include_artifacts=True)],
            )

    def test_default_scan_includes_paper_sources(self) -> None:
        with self.make_repo() as root_name:
            root = Path(root_name)
            aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            paper_path = root / "paper" / "access.tex"
            write_file(paper_path, f"Leaked key: {aws_key}\n")
            subprocess.run(
                ["git", "add", str(paper_path.relative_to(root))],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            findings = scan_secrets.scan_repo(root)

            self.assertEqual(
                [("paper/access.tex", "aws-access-key-id")],
                [(finding.path, finding.rule) for finding in findings],
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
