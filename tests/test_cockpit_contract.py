import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_nexus_tui
from scripts.validate_nexus_cockpit_contract import validate_payload, validate_receipt


class CockpitContractTests(unittest.TestCase):
    def _load(self, path: str) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def test_schema_and_fixture_shapes_validate(self) -> None:
        validate_payload("capabilities", self._load("tests/fixtures/cockpit/capabilities_example.json"))
        validate_payload("action_specs", self._load("tests/fixtures/cockpit/action_specs_example.json"))
        validate_payload("snapshot", self._load("tests/fixtures/cockpit/snapshot_example.json"))
        validate_payload("action", self._load("tests/fixtures/cockpit/action_load_preset.json"))
        validate_payload("action", self._load("tests/fixtures/cockpit/action_enqueue.json"))
        validate_payload("action", self._load("tests/fixtures/cockpit/action_generate_turn_packet.json"))
        validate_payload("result", self._load("tests/fixtures/cockpit/action_result_example.json"))

    def test_real_action_result_and_receipt_validate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session_path = Path(td) / "session.json"
            with mock.patch.object(run_nexus_tui, "SESSION_PATH", session_path):
                with mock.patch.object(run_nexus_tui, "RECEIPTS_DIR", Path(td) / "receipts"):
                    with mock.patch("builtins.print") as mock_print:
                        rc = run_nexus_tui.main([
                            "--action-json",
                            json.dumps({"action": "load_preset", "source": "library", "selection": "1", "topic": "llama throughput"}),
                        ])
                    self.assertEqual(rc, 0)
                    result_payload = json.loads(mock_print.call_args[0][0])
                    validate_payload("result", result_payload)

                    receipt_path = Path(result_payload["receipt_path"])
                    self.assertTrue(receipt_path.exists())
                    validate_receipt(json.loads(receipt_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
