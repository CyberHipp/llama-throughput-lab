import json
import tempfile
import unittest
from pathlib import Path

from llama_nexus_lab.gauntlet import GauntletSpec, build_temp_runtime_config, load_gauntlet_spec, save_gauntlet_spec
from scripts.run_nexus_tui import build_launch_command


class NexusTuiTests(unittest.TestCase):
    def test_gauntlet_save_load_roundtrip(self):
        spec = GauntletSpec(
            gauntlet_name="roundtrip",
            query="test query",
            max_search_intents=3,
            strict_citation_required=True,
            dry_run=True,
            require_verify_pass=False,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "roundtrip.json"
            save_gauntlet_spec(path, spec)
            loaded = load_gauntlet_spec(path)
        self.assertEqual(spec, loaded)

    def test_temp_runtime_config_override_behavior(self):
        spec = GauntletSpec(
            gauntlet_name="override",
            query="test query",
            max_search_intents=7,
            strict_citation_required=False,
            dry_run=True,
            require_verify_pass=False,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "config.json"
            generated_path = build_temp_runtime_config("configs/nexus/default.json", spec, out_path)
            payload = json.loads(Path(generated_path).read_text(encoding="utf-8"))
        self.assertEqual(payload["pipeline"]["max_search_intents"], 7)
        self.assertFalse(payload["pipeline"]["strict_citation_required"])
        self.assertTrue(payload["pipeline"]["dry_run"])

    def test_command_payload_build_in_fallback_mode(self):
        spec = GauntletSpec(
            gauntlet_name="cmd",
            query="test query",
            max_search_intents=2,
            strict_citation_required=True,
            dry_run=True,
            require_verify_pass=False,
        )
        cmd = build_launch_command(spec, "artifacts/nexus/tui_runs/x/config.json")
        self.assertIn("scripts/run_nexus_pipeline.py", " ".join(cmd))
        self.assertIn("--query", cmd)

    def test_invalid_numeric_input_fails_closed(self):
        spec = GauntletSpec(
            gauntlet_name="bad",
            query="test",
            max_search_intents=0,
            strict_citation_required=True,
            dry_run=True,
            require_verify_pass=True,
        )
        with self.assertRaises(ValueError):
            spec.validate()


if __name__ == "__main__":
    unittest.main()
