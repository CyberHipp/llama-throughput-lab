import argparse
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from scripts import run_nexus_governed_smoke, run_nexus_pipeline


class RunnerCliEnvelopeTests(unittest.TestCase):
    def test_pipeline_missing_config_emits_failure_json(self):
        args = argparse.Namespace(query="q", config="configs/nexus/does-not-exist.json")
        with mock.patch("scripts.run_nexus_pipeline.parse_args", return_value=args):
            with mock.patch("builtins.print") as mock_print:
                exit_code = run_nexus_pipeline.main()
        self.assertNotEqual(exit_code, 0)
        rendered = json.loads(mock_print.call_args[0][0])
        self.assertEqual(rendered["status"], "fail")
        self.assertEqual(rendered["config_path"], args.config)
        self.assertTrue(rendered["reason"])
        self.assertTrue(rendered["error_type"])

    def test_governed_require_verify_fail_emits_failure_json(self):
        args = argparse.Namespace(query="q", config="configs/nexus/default.json", require_verify_pass=True)
        fake_config = SimpleNamespace(runtime=SimpleNamespace(artifacts_dir="artifacts/nexus"))
        fake_result = SimpleNamespace(
            run_id="run-1",
            trace_id="trace-1",
            request_id="req-1",
            verification_pass=False,
            verification_reason="insufficient evidence coverage",
            confidence=0.2,
        )
        with mock.patch("scripts.run_nexus_governed_smoke.parse_args", return_value=args):
            with mock.patch("scripts.run_nexus_governed_smoke.load_nexus_config", return_value=fake_config):
                with mock.patch("scripts.run_nexus_governed_smoke.run_research_pipeline", return_value=fake_result):
                    with mock.patch(
                        "scripts.run_nexus_governed_smoke.write_pipeline_artifacts",
                        return_value={"receipt_path": "artifacts/nexus/receipt.json"},
                    ):
                        with mock.patch("builtins.print") as mock_print:
                            exit_code = run_nexus_governed_smoke.main()
        self.assertEqual(exit_code, 1)
        rendered = json.loads(mock_print.call_args[0][0])
        self.assertEqual(rendered["status"], "fail")
        self.assertFalse(rendered["verification_pass"])
        self.assertEqual(rendered["reason"], "insufficient evidence coverage")
        self.assertEqual(rendered["error_type"], "VerificationFailed")

    def test_pipeline_success_emits_success_json(self):
        args = argparse.Namespace(query="q", config="configs/nexus/default.json")
        fake_config = SimpleNamespace(runtime=SimpleNamespace(artifacts_dir="artifacts/nexus"))
        fake_result = SimpleNamespace(
            run_id="run-2",
            trace_id="trace-2",
            request_id="req-2",
            confidence=0.8,
            verification_pass=True,
            verification_reason="coverage ok",
        )
        with mock.patch("scripts.run_nexus_pipeline.parse_args", return_value=args):
            with mock.patch("scripts.run_nexus_pipeline.load_nexus_config", return_value=fake_config):
                with mock.patch("scripts.run_nexus_pipeline.run_research_pipeline", return_value=fake_result):
                    with mock.patch(
                        "scripts.run_nexus_pipeline.write_pipeline_artifacts",
                        return_value={"receipt_path": "artifacts/nexus/receipt.json"},
                    ):
                        with mock.patch("builtins.print") as mock_print:
                            exit_code = run_nexus_pipeline.main()
        self.assertEqual(exit_code, 0)
        rendered = json.loads(mock_print.call_args[0][0])
        self.assertEqual(rendered["status"], "success")
        self.assertEqual(rendered["run_id"], "run-2")
        self.assertEqual(rendered["error_type"], None)


if __name__ == "__main__":
    unittest.main()
