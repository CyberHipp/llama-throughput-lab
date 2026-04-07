import json
import tempfile
import unittest
from pathlib import Path


class CockpitContractTests(unittest.TestCase):
    def _load(self, path: str) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def test_schema_and_fixture_shapes(self) -> None:
        snapshot_schema = self._load("schemas/nexus_cockpit_snapshot_v1.json")
        action_schema = self._load("schemas/nexus_cockpit_action_v1.json")
        result_schema = self._load("schemas/nexus_cockpit_action_result_v1.json")

        snapshot_fixture = self._load("tests/fixtures/cockpit/snapshot_example.json")
        action_fixture = self._load("tests/fixtures/cockpit/action_load_preset.json")
        result_fixture = self._load("tests/fixtures/cockpit/action_result_example.json")

        for field in snapshot_schema["required"]:
            self.assertIn(field, snapshot_fixture)
        for field in action_schema["required"]:
            self.assertIn(field, action_fixture)
        for field in result_schema["required"]:
            self.assertIn(field, result_fixture)

    def test_action_fixtures_are_machine_readable(self) -> None:
        for name in ("action_load_preset.json", "action_enqueue.json", "action_generate_turn_packet.json"):
            payload = self._load(f"tests/fixtures/cockpit/{name}")
            self.assertIn("action", payload)
            self.assertIsInstance(payload["action"], str)


if __name__ == "__main__":
    unittest.main()
