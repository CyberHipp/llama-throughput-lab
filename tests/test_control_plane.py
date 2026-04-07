import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from llama_nexus_lab import control_plane
from llama_nexus_lab.gauntlet import GauntletSpec


class ControlPlaneTests(unittest.TestCase):
    def test_list_and_load_preset_by_name_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            preset_dir = Path(td)
            preset = {
                "gauntlet_name": "sample",
                "query_template": "about {topic}",
                "max_search_intents": 2,
                "strict_citation_required": True,
                "dry_run": True,
                "require_verify_pass": False,
                "mode": "fast",
            }
            (preset_dir / "sample.json").write_text(json.dumps(preset), encoding="utf-8")
            presets = control_plane.list_library_presets(preset_dir)
            self.assertEqual(presets[0]["name"], "sample")

            name = control_plane.resolve_library_selection("1", presets)
            spec, meta = control_plane.load_library_preset(name, topic="llamas", preset_dir=preset_dir)
            self.assertEqual(spec.gauntlet_name, "sample")
            self.assertEqual(spec.query, "about llamas")
            self.assertEqual(meta["mode"], "fast")

    def test_preview_and_launch_shapes(self) -> None:
        spec = GauntletSpec(
            gauntlet_name="g1",
            query="q",
            max_search_intents=2,
            strict_citation_required=True,
            dry_run=True,
            require_verify_pass=False,
        )
        preview = control_plane.build_preview_summary(spec, "run-1", "cfg.json", ["python", "run"])
        self.assertEqual(preview["kind"], "preview")
        self.assertIn("preview_command", preview)

        launch = control_plane.build_launch_summary(
            spec,
            "run-1",
            "cfg.json",
            ["python", "run"],
            {"exit_code": 1, "stderr": "boom"},
        )
        self.assertEqual(launch["reason"], "boom")
        self.assertEqual(launch["command"], ["python", "run"])

    def test_recent_artifacts_returns_structured_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            runs = base / "runs"
            queue = runs / "queue"
            turns = base / "turns"
            (runs / "r1").mkdir(parents=True, exist_ok=True)
            queue.mkdir(parents=True, exist_ok=True)
            (turns / "g1").mkdir(parents=True, exist_ok=True)

            (runs / "r1" / "tui_summary.json").write_text(json.dumps({"kind": "preview", "run_id": "r1"}), encoding="utf-8")
            (queue / "q1_summary.json").write_text(json.dumps({"kind": "queue", "queue_id": "q1"}), encoding="utf-8")
            (turns / "g1" / "turn_1_summary.json").write_text(json.dumps({"kind": "turn_packet", "packet_path": "x"}), encoding="utf-8")

            rows = control_plane.list_recent_artifacts(limit=10, tui_runs_dir=runs, queue_dir=queue, email_turns_dir=turns)
            self.assertTrue(any(row.get("summary", {}).get("kind") == "preview" for row in rows))
            self.assertTrue(any(row.get("summary", {}).get("kind") == "queue" for row in rows))
            self.assertTrue(any(row.get("summary", {}).get("kind") == "turn_packet" for row in rows))

    def test_run_command_parses_last_json_line(self) -> None:
        completed = mock.Mock(returncode=0, stdout='noise\n{"ok": true}\n', stderr="")
        with mock.patch("subprocess.run", return_value=completed):
            payload = control_plane.run_command(["python", "x"])
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
