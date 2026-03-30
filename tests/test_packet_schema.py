import json
import unittest
from pathlib import Path

from throughput_lab.identity import CONTRACT_VERSION, TOOL_NAME

GOLDEN_FILES = [
    "tests/golden/dry_run.packet.json",
    "tests/golden/preflight.packet.json",
    "tests/golden/single_smoke.packet.json",
]

REQUIRED_KEYS = {
    "packet_version",
    "mode",
    "status",
    "run_id",
    "intent",
    "tool_name",
    "receipt_path",
    "failure_summary",
    "next_step",
    "data",
}


class PacketSchemaTests(unittest.TestCase):
    def test_goldens_have_required_keys(self):
        for path in GOLDEN_FILES:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertTrue(REQUIRED_KEYS.issubset(set(payload.keys())), path)

    def test_mode_and_status_domains(self):
        modes = {"dry-run", "preflight-only", "single-smoke"}
        statuses = {"success", "failure"}
        for path in GOLDEN_FILES:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertIn(payload["mode"], modes)
            self.assertIn(payload["status"], statuses)

    def test_receipt_path_nullability_rules(self):
        for path in GOLDEN_FILES:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if payload["mode"] in {"dry-run", "preflight-only"}:
                self.assertIsNone(payload["receipt_path"])
            else:
                self.assertIsInstance(payload["receipt_path"], str)

    def test_identity_and_packet_versions(self):
        for path in GOLDEN_FILES:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(payload["tool_name"], TOOL_NAME)
            self.assertEqual(payload["packet_version"], "1.0")
            self.assertEqual(payload["data"]["contract_version"], CONTRACT_VERSION)


if __name__ == "__main__":
    unittest.main()
