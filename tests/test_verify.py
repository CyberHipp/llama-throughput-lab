import unittest

from llama_nexus_lab.models import EvidenceDocument
from llama_nexus_lab.verify import verify_citation_urls, verify_evidence_coverage


class VerifyTests(unittest.TestCase):
    def test_fail_closed_when_strict_and_no_evidence(self):
        ok, reason, coverage = verify_evidence_coverage(
            "llama throughput routing",
            tuple(),
            strict_citation_required=True,
        )
        self.assertFalse(ok)
        self.assertIn("strict_citation_required", reason)
        self.assertEqual(coverage, 0.0)

    def test_pass_with_reasonable_coverage(self):
        evidence = (
            EvidenceDocument(
                intent="x",
                title="Llama throughput routing guide",
                url="https://example.com/guide",
                snippet="routing and throughput optimization for llama workloads",
                content_hash="abc",
            ),
        )
        ok, _, coverage = verify_evidence_coverage(
            "llama throughput routing",
            evidence,
            strict_citation_required=True,
        )
        self.assertTrue(ok)
        self.assertGreaterEqual(coverage, 0.2)

    def test_strict_mode_passes_with_matching_citation_url(self):
        evidence = (
            EvidenceDocument(
                intent="x",
                title="Guide",
                url="https://example.com/guide",
                snippet="snippet",
                content_hash="a",
            ),
        )
        ok, reason = verify_citation_urls(
            "Citations:\n- https://example.com/guide",
            evidence,
            strict_citation_required=True,
        )
        self.assertTrue(ok)
        self.assertIn("match", reason)

    def test_strict_mode_fails_without_matching_citation_url(self):
        evidence = (
            EvidenceDocument(
                intent="x",
                title="Guide",
                url="https://example.com/guide",
                snippet="snippet",
                content_hash="a",
            ),
        )
        ok, reason = verify_citation_urls(
            "Citations:\n- https://other.example.com/doc",
            evidence,
            strict_citation_required=True,
        )
        self.assertFalse(ok)
        self.assertIn("does not cite evidence urls", reason)


if __name__ == "__main__":
    unittest.main()
