import unittest

from src.proposer import cli as proposer_cli
from src.proposer.guidance_store import GuidanceStore
from src.proposer.prompts import FAILURE_CACHE, _build_prompt, _policy_guidance


class GuidanceStoreTests(unittest.TestCase):
    def test_lookup_returns_snippet(self) -> None:
        store = GuidanceStore.default()
        snippets = store.lookup("no_privileged")
        self.assertTrue(snippets, "expected at least one guidance snippet for no_privileged")
        first = snippets[0]
        text_lower = first.text.lower()
        self.assertTrue(
            "privileg" in text_lower or "pod security" in text_lower,
            "expected guidance text to mention privilege controls or Pod Security",
        )
        self.assertTrue(first.citation, "expected guidance snippet to provide a citation")

    def test_policy_guidance_adds_citation(self) -> None:
        guidance = proposer_cli._policy_guidance("no_privileged")
        self.assertIn("[Source:", guidance)
        self.assertIn("Pod Security", guidance)

    def test_prompt_uses_inline_retry_feedback_before_cached_feedback(self) -> None:
        FAILURE_CACHE.record("det-feedback", "cached verifier failure")
        try:
            prompt = _build_prompt(
                {
                    "id": "det-feedback",
                    "policy_id": "set_requests_limits",
                    "violation_text": "resources are missing",
                    "manifest_yaml": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: demo\n",
                    "retry_feedback": "inline verifier failure",
                }
            )
        finally:
            FAILURE_CACHE.clear("det-feedback")

        self.assertIn("Verifier feedback: inline verifier failure", prompt)
        self.assertNotIn("cached verifier failure", prompt)
        self.assertIn("Return ONLY a valid RFC6902 JSON Patch array.", prompt)

    def test_prompt_includes_cached_feedback_when_retry_feedback_is_absent(self) -> None:
        FAILURE_CACHE.record("det-cache", "missing path /spec/containers/0/resources")
        try:
            prompt = _build_prompt(
                {
                    "id": "det-cache",
                    "policy_id": "set_requests_limits",
                    "violation_text": "resources are missing",
                    "manifest_yaml": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: demo\n",
                }
            )
        finally:
            FAILURE_CACHE.clear("det-cache")

        self.assertIn("Verifier feedback: missing path /spec/containers/0/resources", prompt)
        self.assertIn("Guidance:", prompt)

    def test_fallback_policy_guidance_keeps_service_account_opt_in(self) -> None:
        guidance = _policy_guidance("non_existent_service_account")

        self.assertIn("allow-default-service-account", guidance)
        self.assertIn("=true", guidance)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
