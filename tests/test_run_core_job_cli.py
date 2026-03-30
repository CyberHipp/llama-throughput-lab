import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_core_job


class RunCoreJobCliTests(unittest.TestCase):
    def test_dry_run_envelope_shape(self):
        args = argparse.Namespace(
            intent="contract-dry-run",
            output_dir="artifacts/receipts",
            config_json="tests/fixtures/minimal_run_config.json",
            config_override_json=None,
            dry_run=True,
            single_smoke=False,
            preflight_only=False,
            plan_out=None,
        )
        with mock.patch("scripts.run_core_job.parse_args", return_value=args):
            with mock.patch("builtins.print") as mock_print:
                exit_code = run_core_job.main()
        self.assertEqual(exit_code, 0)
        rendered = json.loads(mock_print.call_args[0][0])
        self.assertEqual(rendered["mode"], "dry-run")
        self.assertEqual(rendered["tool_name"], "llama-throughput-lab")
        self.assertIn("contract_version", rendered["data"])

    def test_preflight_only_envelope_shape(self):
        args = argparse.Namespace(
            intent="contract-preflight",
            output_dir="artifacts/receipts",
            config_json="tests/fixtures/minimal_run_config.json",
            config_override_json=None,
            dry_run=False,
            single_smoke=False,
            preflight_only=True,
            plan_out=None,
        )
        with mock.patch("scripts.run_core_job.parse_args", return_value=args):
            with mock.patch("builtins.print") as mock_print:
                exit_code = run_core_job.main()
        self.assertEqual(exit_code, 1)
        rendered = json.loads(mock_print.call_args[0][0])
        self.assertEqual(rendered["mode"], "preflight-only")
        self.assertIsNone(rendered["receipt_path"])

    def test_unknown_override_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_override = Path(tmp_dir) / "bad_override.json"
            bad_override.write_text('{"unknown_key": 1}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                run_core_job.load_config_with_optional_override(
                    "tests/fixtures/minimal_run_config.json",
                    str(bad_override),
                )

    def test_override_merge_behaves_as_intended(self):
        config = run_core_job.load_config_with_optional_override(
            "tests/fixtures/minimal_run_config.json",
            "tests/fixtures/minimal_override.json",
        )
        self.assertEqual(config.port, 18081)

    def test_single_smoke_envelope_wrapping_with_mock(self):
        args = argparse.Namespace(
            intent="contract-single-smoke",
            output_dir="artifacts/receipts",
            config_json="tests/fixtures/minimal_run_config.json",
            config_override_json=None,
            dry_run=False,
            single_smoke=True,
            preflight_only=False,
            plan_out=None,
        )
        fake_result = mock.Mock(
            run_id="run-smoke-001",
            receipt_path="artifacts/receipts/run-smoke-001.receipt.json",
            response_path="artifacts/receipts/run-smoke-001.response.json",
            overall_verification_pass=True,
        )
        fake_receipt = {
            "TIMESTAMP_UTC": "2026-03-29T00:00:00Z",
            "failure_summary": "none",
            "next_step": "Promote this receipt to operator review and wire into TUI adapter.",
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            receipt_path = Path(tmp_dir) / "smoke.receipt.json"
            receipt_path.write_text(json.dumps(fake_receipt), encoding="utf-8")
            fake_result.receipt_path = str(receipt_path)
            fake_result.response_path = str(Path(tmp_dir) / "smoke.response.json")
            with mock.patch("scripts.run_core_job.parse_args", return_value=args):
                with mock.patch("scripts.run_core_job.execute_single_smoke_with_receipt", return_value=fake_result):
                    with mock.patch("builtins.print") as mock_print:
                        exit_code = run_core_job.main()
        self.assertEqual(exit_code, 0)
        rendered = json.loads(mock_print.call_args[0][0])
        self.assertEqual(rendered["mode"], "single-smoke")
        self.assertEqual(rendered["status"], "success")
        self.assertIn("contract_version", rendered["data"])


if __name__ == "__main__":
    unittest.main()
