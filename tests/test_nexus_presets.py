import json
import unittest
from pathlib import Path


class NexusPresetTests(unittest.TestCase):
    def test_preset_files_are_valid(self):
        preset_dir = Path("configs/nexus/gauntlets/presets")
        required = {
            "gauntlet_name",
            "query_template",
            "max_search_intents",
            "strict_citation_required",
            "dry_run",
            "require_verify_pass",
        }
        preset_files = sorted(preset_dir.glob("*.json"))
        self.assertGreaterEqual(len(preset_files), 4)
        for path in preset_files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(required.issubset(set(payload.keys())), str(path))
            self.assertGreater(int(payload["max_search_intents"]), 0)


if __name__ == "__main__":
    unittest.main()
