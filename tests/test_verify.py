import unittest

from llama_nexus_lab.models import EvidenceDocument
from llama_nexus_lab.verify import verify_answer


class VerifyTests(unittest.TestCase):
    def test_verify_requires_citations_when_strict(self):
        status, details = verify_answer(
            answer="No citations here",
            confidence="medium",
            evidence=[EvidenceDocument(intent="x", title="t", url="u", snippet="s", content_hash="h")],
            strict_citation_required=True,
        )
        self.assertEqual(status, "fail")
        self.assertIn("missing_citations", details["blockers"])


if __name__ == "__main__":
    unittest.main()
