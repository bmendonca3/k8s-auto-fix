import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.proposer.cli import _generate_patch_record
from src.proposer.response_cache import build_response_cache_metadata


SAMPLE_MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: demo
spec:
  containers:
    - name: app
      image: nginx:latest
"""

PATCH_RESPONSE = '[{"op":"replace","path":"/spec/containers/0/image","value":"nginx:stable"}]'


class CountingModelGenerator:
    source = "vendor"

    def __init__(self, response=PATCH_RESPONSE) -> None:
        self.calls = 0
        self.response = response

    def __call__(self, _detection, _rng):
        self.calls += 1
        return {"content": self.response, "usage": {"total_tokens": 7}}


def _detection():
    return {
        "id": "cache-001",
        "policy_id": "no_latest_tag",
        "violation_text": "container uses latest tag",
        "manifest_yaml": SAMPLE_MANIFEST,
    }


def _vendor_config(cache_dir=None, model="demo-model"):
    config = {
        "seed": 17,
        "proposer": {"mode": "vendor", "timeout_seconds": 3, "retries": 1},
        "vendor": {"endpoint": "http://model.invalid", "model": model},
    }
    if cache_dir is not None:
        config["proposer"]["cache_dir"] = str(cache_dir)
    return config


class ProposerResponseCacheTests(unittest.TestCase):
    def test_no_cache_fields_or_reuse_without_cache_config(self) -> None:
        generator = CountingModelGenerator()

        first = _generate_patch_record(
            _detection(),
            config_data=_vendor_config(),
            base_dir=Path("."),
            generator=generator,
            max_attempts=1,
        )
        second = _generate_patch_record(
            _detection(),
            config_data=_vendor_config(),
            base_dir=Path("."),
            generator=generator,
            max_attempts=1,
        )

        self.assertEqual(generator.calls, 2)
        self.assertNotIn("cache_hit", first)
        self.assertNotIn("cache_key", second)

    def test_cache_miss_stores_response_and_hit_skips_generator(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = _vendor_config(cache_dir=tmpdir)
            generator = CountingModelGenerator()

            first = _generate_patch_record(
                _detection(),
                config_data=config,
                base_dir=Path("."),
                generator=generator,
                max_attempts=1,
            )
            cache_path = Path(first["cache_path"])
            cached_payload = json.loads(cache_path.read_text(encoding="utf-8"))

            self.assertEqual(generator.calls, 1)
            self.assertFalse(first["cache_hit"])
            self.assertEqual(cached_payload["raw_response"], PATCH_RESPONSE)
            self.assertEqual(cached_payload["cache_key"], first["cache_key"])

            miss_detector = CountingModelGenerator()
            second = _generate_patch_record(
                _detection(),
                config_data=config,
                base_dir=Path("."),
                generator=miss_detector,
                max_attempts=1,
            )

            self.assertEqual(miss_detector.calls, 0)
            self.assertTrue(second["cache_hit"])
            self.assertEqual(second["cache_key"], first["cache_key"])
            self.assertEqual(second["cache_path"], first["cache_path"])
            self.assertEqual(second["patch"], first["patch"])

    def test_rules_generator_ignores_cache_config(self) -> None:
        with TemporaryDirectory() as tmpdir:
            result = _generate_patch_record(
                _detection(),
                config_data={"proposer": {"mode": "rules", "cache_dir": tmpdir}},
                base_dir=Path("."),
                max_attempts=1,
            )

            self.assertNotIn("cache_hit", result)
            self.assertEqual(list(Path(tmpdir).iterdir()), [])

    def test_invalid_model_response_is_not_cached(self) -> None:
        invalid_response = '[{"op":"replace","path":"/spec/containers/9/image","value":"nginx:stable"}]'
        with TemporaryDirectory() as tmpdir:
            generator = CountingModelGenerator(response=invalid_response)
            result = _generate_patch_record(
                _detection(),
                config_data=_vendor_config(cache_dir=tmpdir),
                base_dir=Path("."),
                generator=generator,
                max_attempts=1,
            )

            self.assertEqual(generator.calls, 1)
            self.assertNotIn("cache_hit", result)
            self.assertEqual(list(Path(tmpdir).iterdir()), [])

    def test_cache_key_changes_for_retry_feedback_and_model_config(self) -> None:
        base_detection = {
            "policy_id": "no_latest_tag",
            "manifest_yaml": SAMPLE_MANIFEST,
            "violation_text": "container uses latest tag",
        }
        base_config = {"source": "vendor", "mode": "vendor", "model": "demo-a"}
        without_feedback = build_response_cache_metadata(
            detection=base_detection,
            generator_config=base_config,
            prompt="prompt without retry feedback",
        )
        with_feedback_detection = dict(base_detection)
        with_feedback_detection["retry_feedback"] = "missing path /spec/containers/9/image"
        with_feedback = build_response_cache_metadata(
            detection=with_feedback_detection,
            generator_config=base_config,
            prompt="prompt with retry feedback",
        )
        changed_model = build_response_cache_metadata(
            detection=base_detection,
            generator_config={**base_config, "model": "demo-b"},
            prompt="prompt without retry feedback",
        )

        self.assertNotEqual(without_feedback.key, with_feedback.key)
        self.assertNotEqual(without_feedback.input_hash, with_feedback.input_hash)
        self.assertNotEqual(without_feedback.key, changed_model.key)
        self.assertNotEqual(without_feedback.config_hash, changed_model.config_hash)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
