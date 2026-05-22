import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_README = ROOT / "configs" / "README.md"
CONFIG_PATH_RE = re.compile(r"`(configs/[^`]+\.ya?ml)`")


class ConfigDocsTests(unittest.TestCase):
    def test_documented_config_files_exist(self) -> None:
        content = CONFIG_README.read_text(encoding="utf-8")
        documented_paths = sorted(set(CONFIG_PATH_RE.findall(content)))

        self.assertTrue(documented_paths, "expected config docs to mention YAML config paths")
        missing = [path for path in documented_paths if not (ROOT / path).is_file()]
        self.assertEqual([], missing)

    def test_checked_in_yaml_configs_are_documented(self) -> None:
        content = CONFIG_README.read_text(encoding="utf-8")
        config_paths = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "configs").glob("*.yaml")
        )

        self.assertTrue(config_paths, "expected checked-in YAML configs")
        for config_path in config_paths:
            self.assertIn(f"`{config_path}`", content)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
