import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import check_docs_links


class CheckDocsLinksTests(unittest.TestCase):
    def test_valid_local_file_and_anchor_links_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            (docs / "guide.md").write_text(
                "Guide\n=====\n\n## Install Notes\n\nContent.\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text(
                "# Project\n\n"
                "See [guide](docs/guide.md#guide), [notes](docs/guide.md#install-notes), "
                "and [top](#project).\n",
                encoding="utf-8",
            )

            result = check_docs_links.check_paths([root], root=root)

            self.assertTrue(result.ok)
            self.assertEqual(2, result.files_checked)
            self.assertEqual(3, result.links_checked)

    def test_missing_relative_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / "README.md"
            readme.write_text("# Project\n\n[missing](docs/missing.md)\n", encoding="utf-8")

            result = check_docs_links.check_paths([readme], root=root)

            self.assertFalse(result.ok)
            self.assertEqual(1, len(result.issues))
            self.assertIn("missing target", result.issues[0].message)

    def test_missing_heading_anchor_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / "README.md"
            readme.write_text("# Project\n\n[bad](#does-not-exist)\n", encoding="utf-8")

            result = check_docs_links.check_paths([readme], root=root)

            self.assertFalse(result.ok)
            self.assertEqual("missing anchor #does-not-exist", result.issues[0].message)

    def test_external_and_mailto_links_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / "README.md"
            readme.write_text(
                "# Project\n\n"
                "[external](https://example.com/nope#missing)\n"
                "[mail](mailto:docs@example.com#topic)\n"
                "[root absolute](/external/docs/path)\n",
                encoding="utf-8",
            )

            result = check_docs_links.check_paths([root], root=root)

            self.assertTrue(result.ok)
            self.assertEqual(0, result.links_checked)

    def test_cli_report_is_concise_and_nonzero_on_broken_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / "README.md"
            readme.write_text("# Project\n\n[bad](missing.md)\n", encoding="utf-8")
            stdout = io.StringIO()

            with mock.patch("scripts.check_docs_links.Path.cwd", return_value=root):
                with redirect_stdout(stdout):
                    exit_code = check_docs_links.main([str(readme)])

            output = stdout.getvalue()
            self.assertEqual(1, exit_code)
            self.assertIn("Broken local Markdown links:", output)
            self.assertIn("README.md:3", output)
            self.assertIn("1 broken", output)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
