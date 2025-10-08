import unittest

from src.proposer import cli as proposer_cli
from src.proposer.guidance_store import GuidanceStore


class GuidanceStoreTests(unittest.TestCase):
    def test_lookup_returns_snippet(self) -> None:
        store = GuidanceStore.default()
        snippets = store.lookup("no_privileged")
        self.assertTrue(snippets, "expected at least one guidance snippet for no_privileged")
        first = snippets[0]
        self.assertIn("privileged", first.text.lower())
        self.assertIn("kubernetes.io", first.citation)

    def test_policy_guidance_adds_citation(self) -> None:
        guidance = proposer_cli._policy_guidance("no_privileged")
        self.assertIn("[Source:", guidance)
        self.assertIn("Pod Security", guidance)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
