import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from llama_nexus_lab.gauntlet import GauntletSpec, build_temp_runtime_config, load_gauntlet_spec, save_gauntlet_spec
from scripts.run_nexus_tui import (
    _build_launch_summary,
    _persist_queue_summary,
    _persist_run_summary,
    _persist_turn_summary,
    _library_preset_info,
    _load_library_preset,
    _parse_source,
    _resolve_library_selection,
    _show_recent_artifacts,
    _new_state,
    _execute_action,
    _screen_item_count,
    build_launch_command,
)
from scripts import run_nexus_tui


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

    def test_invalid_source_input_rejected(self):
        with self.assertRaises(ValueError):
            _parse_source("anything-else")

    def test_missing_library_preset_reports_available_list(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            _load_library_preset("__does_not_exist__")
        self.assertIn("Available presets:", str(ctx.exception))

    def test_library_preset_helper_returns_known_presets(self):
        presets = _library_preset_info()
        names = [row["name"] for row in presets]
        self.assertIn("vortex_fast_scan", names)

    def test_library_select_by_exact_name(self):
        presets = _library_preset_info()
        selected = _resolve_library_selection("vortex_fast_scan", presets)
        self.assertEqual(selected, "vortex_fast_scan")

    def test_library_select_by_numeric_index(self):
        presets = _library_preset_info()
        selected = _resolve_library_selection("1", presets)
        self.assertEqual(selected, presets[0]["name"])

    def test_library_select_out_of_range_fails_closed(self):
        presets = _library_preset_info()
        with self.assertRaises(ValueError) as ctx:
            _resolve_library_selection("99", presets)
        self.assertIn("Available presets:", str(ctx.exception))

    def test_loaded_summary_includes_metadata(self):
        with mock.patch("builtins.input", return_value="llama throughput"):
            spec, preset_meta = _load_library_preset("vortex_fast_scan")
        summary = {"status": "loaded", "gauntlet_name": spec.gauntlet_name}
        summary.update({key: value for key, value in preset_meta.items() if value is not None})
        self.assertEqual(summary["gauntlet_name"], "vortex_fast_scan")
        self.assertIn("mode", summary)
        self.assertIn("risk_level", summary)
        self.assertIn("notes", summary)

    def test_launch_summary_includes_stderr_command_on_failure(self):
        spec = GauntletSpec(
            gauntlet_name="fail",
            query="test query",
            max_search_intents=2,
            strict_citation_required=True,
            dry_run=True,
            require_verify_pass=False,
        )
        payload = {"exit_code": 1, "stderr": "boom"}
        cmd = ["python", "scripts/run_nexus_pipeline.py", "--query", "q"]
        summary = _build_launch_summary(spec, "run-1", "config.json", cmd, payload)
        self.assertEqual(summary["command"], cmd)
        self.assertEqual(summary["stderr"], "boom")
        self.assertEqual(summary["reason"], "boom")



    def test_inline_action_helper_is_deterministic(self):
        state = _new_state()
        prompts = iter(["library", "1", "llama throughput"])
        should_exit, result = _execute_action("2", state, prompt=lambda _label: next(prompts))
        self.assertFalse(should_exit)
        self.assertEqual(result["status"], "loaded")
        self.assertIsNotNone(state["loaded_spec"])

    def test_screen_item_count_helper(self):
        snapshot = {
            "presets": {"count": 3},
            "queue": {"queue_size": 2},
            "artifacts": {"count": 4},
            "turn_packets": {"count": 0},
        }
        self.assertEqual(_screen_item_count(snapshot, "Presets"), 3)
        self.assertEqual(_screen_item_count(snapshot, "Queue"), 2)
        self.assertEqual(_screen_item_count(snapshot, "Turn Packets"), 1)

    def test_dump_state_returns_machine_readable_snapshot(self):
        with mock.patch("builtins.print") as mock_print:
            exit_code = run_nexus_tui.main(["--dump-state"])
        self.assertEqual(exit_code, 0)
        rendered = mock_print.call_args[0][0]
        payload = json.loads(rendered)
        self.assertIn("screens", payload)
        self.assertIn("presets", payload)
        self.assertIn("queue", payload)
        self.assertIn("artifacts", payload)
        self.assertIn("turn_packets", payload)
        self.assertIn("cockpit", payload)
        self.assertIn("loaded_gauntlet", payload["cockpit"])
        self.assertIn("last_action_result", payload["cockpit"])


    def test_action_bridge_load_preview_enqueue_and_failure(self):
        with tempfile.TemporaryDirectory() as td:
            session = Path(td) / "session.json"
            with mock.patch.object(run_nexus_tui, "SESSION_PATH", session):
                with mock.patch("builtins.print") as mock_print:
                    rc = run_nexus_tui.main(["--action-json", json.dumps({"action": "load_preset", "source": "library", "selection": "1", "topic": "llama throughput"})])
                self.assertEqual(rc, 0)
                payload = json.loads(mock_print.call_args[0][0])
                self.assertEqual(payload["status"], "ok")

                with mock.patch("builtins.print") as mock_print:
                    rc = run_nexus_tui.main(["--action-json", json.dumps({"action": "enqueue"})])
                self.assertEqual(rc, 0)
                enqueue_payload = json.loads(mock_print.call_args[0][0])
                self.assertEqual(enqueue_payload["status"], "ok")

                with mock.patch("scripts.run_nexus_tui.control_plane.run_queue", return_value={"status": "completed", "kind": "queue"}):
                    with mock.patch("builtins.print") as mock_print:
                        rc = run_nexus_tui.main(["--action-json", json.dumps({"action": "run_queue", "stop_on_fail": True})])
                self.assertEqual(rc, 0)
                runq_payload = json.loads(mock_print.call_args[0][0])
                self.assertEqual(runq_payload["result"]["kind"], "queue")

                with mock.patch("builtins.print") as mock_print:
                    rc = run_nexus_tui.main(["--action-json", json.dumps({"action": "unknown_action"})])
                self.assertEqual(rc, 1)
                err_payload = json.loads(mock_print.call_args[0][0])
                self.assertEqual(err_payload["status"], "error")
                self.assertIn("error_type", err_payload)

    def test_action_bridge_generate_turn_packet(self):
        with tempfile.TemporaryDirectory() as td:
            session = Path(td) / "session.json"
            with mock.patch.object(run_nexus_tui, "SESSION_PATH", session):
                with mock.patch("builtins.print") as mock_print:
                    rc = run_nexus_tui.main(["--action-json", json.dumps({"action": "generate_turn_packet", "game_id": "g1", "turn": 2, "move": "e4", "actor": "op", "fen": "startpos"})])
            self.assertEqual(rc, 0)
            payload = json.loads(mock_print.call_args[0][0])
            self.assertEqual(payload["status"], "ok")
            self.assertIn("packet_path", payload["result"])

    def test_non_interactive_fallback_smoke_preview(self):
        inputs = iter(
            [
                "2",  # menu: load preset
                "library",
                "4",
                "llama throughput",
                "3",  # menu: dry-run preview
                "9",  # menu: exit
            ]
        )
        with mock.patch("sys.stdin.isatty", return_value=False):
            with mock.patch("builtins.input", side_effect=lambda _prompt="": next(inputs)):
                with mock.patch("builtins.print") as mock_print:
                    exit_code = run_nexus_tui.main()
        self.assertEqual(exit_code, 0)
        json_rows = []
        for call in mock_print.call_args_list:
            rendered = call.args[0] if call.args else ""
            try:
                json_rows.append(json.loads(rendered))
            except (TypeError, json.JSONDecodeError):
                continue
        preview_rows = [row for row in json_rows if "preview_command" in row]
        self.assertTrue(preview_rows)
        preview = preview_rows[-1]
        self.assertIn("gauntlet_name", preview)
        self.assertIn("config_path", preview)
        self.assertIn("preview_command", preview)

    def test_preview_summary_file_is_written(self):
        payload = {
            "kind": "preview",
            "status": "preview",
            "run_id": "tui-preview-1",
            "gauntlet_name": "vortex_fast_scan",
            "config_path": "artifacts/nexus/tui_runs/tui-preview-1/config.json",
            "command": ["python", "scripts/run_nexus_pipeline.py"],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            with mock.patch.object(run_nexus_tui, "TUI_RUNS_DIR", Path(tmp_dir)):
                path = _persist_run_summary("tui-preview-1", payload)
                self.assertTrue(Path(path).exists())
                saved = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(saved["kind"], "preview")
        self.assertEqual(saved["run_id"], "tui-preview-1")

    def test_launch_summary_file_is_written_with_expected_keys(self):
        spec = GauntletSpec(
            gauntlet_name="launch",
            query="q",
            max_search_intents=2,
            strict_citation_required=False,
            dry_run=True,
            require_verify_pass=False,
        )
        payload = {"exit_code": 1, "stderr": "boom"}
        command = ["python", "scripts/run_nexus_pipeline.py"]
        summary = _build_launch_summary(spec, "tui-launch-1", "config.json", command, payload)
        summary["kind"] = "launch"
        summary["status"] = "fail"
        with tempfile.TemporaryDirectory() as tmp_dir:
            with mock.patch.object(run_nexus_tui, "TUI_RUNS_DIR", Path(tmp_dir)):
                path = _persist_run_summary("tui-launch-1", summary)
                saved = json.loads(Path(path).read_text(encoding="utf-8"))
        for key in ("kind", "status", "run_id", "config_path", "command", "stderr", "reason"):
            self.assertIn(key, saved)

    def test_queue_summary_file_is_written(self):
        payload = {"kind": "queue", "status": "completed", "queue_id": "queue-123", "manifest_path": "m.json", "receipt_path": "r.json"}
        with tempfile.TemporaryDirectory() as tmp_dir:
            queue_dir = Path(tmp_dir) / "queue"
            with mock.patch.object(run_nexus_tui, "QUEUE_DIR", queue_dir):
                path = _persist_queue_summary("queue-123", payload)
                self.assertTrue(Path(path).exists())
                saved = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(saved["queue_id"], "queue-123")

    def test_turn_packet_summary_file_is_written(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            packet_path = Path(tmp_dir) / "game-1" / "turn_1.json"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text("{}", encoding="utf-8")
            summary_path = _persist_turn_summary(str(packet_path), {"kind": "turn_packet", "status": "generated", "packet_path": str(packet_path)})
            self.assertTrue(Path(summary_path).exists())
            saved = json.loads(Path(summary_path).read_text(encoding="utf-8"))
        self.assertEqual(saved["kind"], "turn_packet")

    def test_recent_artifacts_returns_structured_summaries(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            runs = base / "tui_runs"
            queue = runs / "queue"
            turns = base / "email_turns"
            (runs / "tui-1").mkdir(parents=True, exist_ok=True)
            (turns / "game-1").mkdir(parents=True, exist_ok=True)
            (queue).mkdir(parents=True, exist_ok=True)
            (runs / "tui-1" / "tui_summary.json").write_text(json.dumps({"kind": "preview", "run_id": "tui-1"}), encoding="utf-8")
            (queue / "queue-1_summary.json").write_text(json.dumps({"kind": "queue", "queue_id": "queue-1"}), encoding="utf-8")
            (turns / "game-1" / "turn_1_summary.json").write_text(json.dumps({"kind": "turn_packet", "packet_path": "x"}), encoding="utf-8")
            with mock.patch.object(run_nexus_tui, "TUI_RUNS_DIR", runs):
                with mock.patch.object(run_nexus_tui, "QUEUE_DIR", queue):
                    with mock.patch.object(run_nexus_tui, "EMAIL_TURNS_DIR", turns):
                        recent = _show_recent_artifacts(limit=10)
        self.assertGreaterEqual(len(recent), 3)
        self.assertTrue(any(row.get("summary", {}).get("kind") == "preview" for row in recent))
        self.assertTrue(any(row.get("summary", {}).get("kind") == "queue" for row in recent))
        self.assertTrue(any(row.get("summary", {}).get("kind") == "turn_packet" for row in recent))


if __name__ == "__main__":
    unittest.main()
