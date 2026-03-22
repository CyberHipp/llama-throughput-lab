import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from throughput_lab.execution_core import (
    EndpointMode,
    RunConfig,
    TopologyMode,
    VerificationMode,
    build_run_plan,
    dry_run_packet,
    execute_single_smoke_with_receipt,
    parse_smoke_response,
    preflight_packet,
    run_preflight_checks,
    run_with_receipt,
    verify_smoke_response,
)


class _FakeHTTPResponse:
    def __init__(self, status: int, payload: dict | None = None):
        self.status = status
        self._payload = payload or {}

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


class PreflightTests(unittest.TestCase):
    def test_preflight_failure_on_missing_model_path(self):
        cfg = RunConfig(
            model_path="/missing/model.gguf",
            llama_server_bin="/missing/llama-server",
            topology_mode=TopologyMode.SINGLE,
        )
        result = run_preflight_checks(cfg)
        self.assertEqual(result["result"], "fail")
        check_names = {c["name"]: c["result"] for c in result["checks"]}
        self.assertEqual(check_names["model_path_exists"], "fail")

    def test_preflight_failure_on_unsupported_topology(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            model = Path(tmp_dir) / "model.gguf"
            server = Path(tmp_dir) / "llama-server"
            model.write_text("x", encoding="utf-8")
            _make_executable(server)
            cfg = RunConfig(
                model_path=str(model),
                llama_server_bin=str(server),
                topology_mode=TopologyMode.ROUND_ROBIN,
            )
            result = run_preflight_checks(cfg)

        self.assertEqual(result["result"], "fail")
        check_names = {c["name"]: c["result"] for c in result["checks"]}
        self.assertEqual(check_names["topology_allowed_for_smoke"], "fail")

    def test_preflight_catches_missing_request_model_for_openai_mode(self):
        cfg = RunConfig(
            model_path="/missing/model.gguf",
            llama_server_bin="/missing/llama-server",
            topology_mode=TopologyMode.SINGLE,
            endpoint_mode=EndpointMode.CHAT_COMPLETIONS,
            request_model=None,
        )
        result = run_preflight_checks(cfg)
        check_names = {c["name"]: c["result"] for c in result["checks"]}
        self.assertEqual(check_names["request_model_compatibility"], "fail")

    def test_preflight_catches_missing_expected_text_for_exact(self):
        cfg = RunConfig(
            model_path="/missing/model.gguf",
            llama_server_bin="/missing/llama-server",
            topology_mode=TopologyMode.SINGLE,
            verification_mode=VerificationMode.EXACT,
            expected_text=None,
        )
        result = run_preflight_checks(cfg)
        check_names = {c["name"]: c["result"] for c in result["checks"]}
        self.assertEqual(check_names["verification_expected_text_compatibility"], "fail")

    def test_preflight_accepts_path_resolved_executable_name(self):
        cfg = RunConfig(
            model_path="/missing/model.gguf",
            llama_server_bin="python3",
            topology_mode=TopologyMode.SINGLE,
        )
        result = run_preflight_checks(cfg)
        check_names = {c["name"]: c["result"] for c in result["checks"]}
        self.assertEqual(check_names["llama_server_bin_executable"], "pass")


class ResponseParsingTests(unittest.TestCase):
    def test_parse_completion_response(self):
        text = parse_smoke_response(EndpointMode.COMPLETION, {"content": "hello world"})
        self.assertEqual(text, "hello world")

    def test_parse_chat_completions_response(self):
        payload = {"choices": [{"message": {"content": "chat hello"}}]}
        text = parse_smoke_response(EndpointMode.CHAT_COMPLETIONS, payload)
        self.assertEqual(text, "chat hello")

    def test_parse_v1_completions_response(self):
        payload = {"choices": [{"text": "classic completion"}]}
        text = parse_smoke_response(EndpointMode.V1_COMPLETIONS, payload)
        self.assertEqual(text, "classic completion")


class VerificationModeTests(unittest.TestCase):
    def test_non_empty_pass_and_fail(self):
        self.assertEqual(verify_smoke_response("ok", VerificationMode.NON_EMPTY, None)[0], True)
        self.assertEqual(verify_smoke_response("   ", VerificationMode.NON_EMPTY, None)[0], False)

    def test_exact_pass_and_fail(self):
        self.assertEqual(verify_smoke_response("abc", VerificationMode.EXACT, "abc")[0], True)
        self.assertEqual(verify_smoke_response("abc", VerificationMode.EXACT, "xyz")[0], False)


class PayloadContractTests(unittest.TestCase):
    def test_openai_chat_payload_requires_and_includes_model(self):
        cfg = RunConfig(
            model_path="/tmp/model.gguf",
            llama_server_bin="/tmp/llama-server",
            endpoint_mode=EndpointMode.CHAT_COMPLETIONS,
            request_model="llama-3b-smoke",
            prompt="hello",
        )
        payload = cfg.build_request_payload()
        self.assertEqual(payload["model"], "llama-3b-smoke")

    def test_native_completion_payload_is_minimal(self):
        cfg = RunConfig(
            model_path="/tmp/model.gguf",
            llama_server_bin="/tmp/llama-server",
            endpoint_mode=EndpointMode.COMPLETION,
            prompt="hello",
            request_model=None,
        )
        payload = cfg.build_request_payload()
        self.assertIn("prompt", payload)
        self.assertNotIn("model", payload)


class PlanAndReceiptTests(unittest.TestCase):
    def test_dry_run_failure_returns_structured_packet(self):
        cfg = RunConfig(
            model_path="/tmp/model.gguf",
            llama_server_bin="/tmp/llama-server",
            endpoint_mode=EndpointMode.CHAT_COMPLETIONS,
            request_model=None,
        )
        packet, exit_code = dry_run_packet(cfg, output_dir="/tmp", intent="dry-run-fail")
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["mode"], "dry-run")
        self.assertEqual(packet["status"], "failure")
        self.assertIn("failure_summary", packet)
        self.assertIsNone(packet["receipt_path"])

    @mock.patch("throughput_lab.execution_core.subprocess.check_output")
    def test_dry_run_packet_includes_preflight_and_verification(self, mock_rev_parse):
        mock_rev_parse.return_value = "abc123\n"
        cfg = RunConfig(
            model_path="/models/model.gguf",
            llama_server_bin="/bin/llama-server",
            endpoint_mode=EndpointMode.CHAT_COMPLETIONS,
            topology_mode=TopologyMode.SINGLE,
            verification_mode=VerificationMode.NON_EMPTY,
            request_model="llama-3b-smoke",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan = build_run_plan(cfg, output_dir=tmp_dir, intent="smoke")

        self.assertIn("preflight_targets", plan)
        self.assertIn("expected_response_policy", plan)
        self.assertIn("expected_artifact_set", plan)
        self.assertEqual(plan["verification_mode"], "NON_EMPTY")

    def test_preflight_target_set_matches_effective_checks(self):
        cfg = RunConfig(
            model_path="/models/model.gguf",
            llama_server_bin="/bin/llama-server",
            topology_mode=TopologyMode.SINGLE,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan = build_run_plan(cfg, output_dir=tmp_dir, intent="smoke")
        check_names = {
            "model_path_exists",
            "llama_server_bin_executable",
            "topology_allowed_for_smoke",
            "target_port_available",
            "request_model_compatibility",
            "verification_expected_text_compatibility",
            "request_payload_buildable",
        }
        self.assertEqual(set(plan["preflight_targets"]), check_names)

    def test_runtime_env_appears_in_plan(self):
        cfg = RunConfig(
            model_path="/models/model.gguf",
            llama_server_bin="/bin/llama-server",
            endpoint_mode=EndpointMode.COMPLETION,
            topology_mode=TopologyMode.SINGLE,
            runtime_env={"CUDA_VISIBLE_DEVICES": "0"},
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan = build_run_plan(cfg, output_dir=tmp_dir, intent="smoke")
        self.assertEqual(plan["resolved_runtime_env"]["CUDA_VISIBLE_DEVICES"], "0")

    @mock.patch("throughput_lab.execution_core.subprocess.run")
    @mock.patch("throughput_lab.execution_core.subprocess.check_output")
    def test_run_with_receipt_writes_artifacts(self, mock_rev_parse, mock_run):
        mock_rev_parse.return_value = "abc123\n"
        mock_run.return_value = mock.Mock(returncode=0)

        cfg = RunConfig(
            model_path="/models/model.gguf",
            llama_server_bin="/bin/llama-server",
            topology_mode=TopologyMode.SINGLE,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = run_with_receipt(cfg, output_dir=tmp_dir, intent="smoke")
            receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))

        self.assertEqual(receipt["INTENT"], "smoke")
        self.assertEqual(receipt["PINNED_COMMIT"], "abc123")
        self.assertEqual(receipt["verification_result"], "pass")


class SmokeExecutionTests(unittest.TestCase):
    @mock.patch("throughput_lab.execution_core.subprocess.check_output", return_value="abc123\n")
    @mock.patch("throughput_lab.runtime_service.subprocess.Popen")
    @mock.patch("throughput_lab.runtime_service.urllib.request.urlopen")
    def test_receipt_completeness_for_smoke_verification_fields(self, mock_urlopen, mock_popen, _mock_rev_parse):
        process = mock.Mock()
        process.wait.return_value = -15
        mock_popen.return_value = process

        def _urlopen_side_effect(req, timeout=2):
            if isinstance(req, str):
                return _FakeHTTPResponse(200, {"status": "ok"})
            return _FakeHTTPResponse(
                200,
                {
                    "content": "deterministic smoke ok",
                    "timings": {"predicted_n": 8, "predicted_per_second": 12.5},
                },
            )

        mock_urlopen.side_effect = _urlopen_side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            model = Path(tmp_dir) / "model.gguf"
            server = Path(tmp_dir) / "llama-server"
            model.write_text("x", encoding="utf-8")
            _make_executable(server)

            cfg = RunConfig(
                model_path=str(model),
                llama_server_bin=str(server),
                endpoint_mode=EndpointMode.COMPLETION,
                topology_mode=TopologyMode.SINGLE,
                verification_mode=VerificationMode.NON_EMPTY,
            )

            result = execute_single_smoke_with_receipt(cfg, output_dir=tmp_dir, intent="3b-smoke")
            receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))

        required_fields = [
            "preflight_verification_result",
            "readiness_verification_result",
            "response_parse_result",
            "semantic_verification_result",
            "overall_verification_result",
            "response_summary",
            "extracted_response_text_preview",
            "verification_mode",
            "expected_text",
            "failure_summary",
            "next_step",
        ]
        for field in required_fields:
            self.assertIn(field, receipt)
        self.assertEqual(receipt["overall_verification_result"], "pass")
        self.assertTrue(receipt["response_summary"]["response_text_present"])
        self.assertEqual(receipt["controlled_shutdown_result"], "pass")

    @mock.patch("throughput_lab.execution_core.subprocess.check_output", return_value="abc123\n")
    @mock.patch("throughput_lab.runtime_service.subprocess.Popen")
    @mock.patch("throughput_lab.runtime_service.urllib.request.urlopen")
    def test_controlled_shutdown_is_stricter_for_kill_exit(self, mock_urlopen, mock_popen, _mock_rev_parse):
        process = mock.Mock()
        process.wait.return_value = -9
        mock_popen.return_value = process

        def _urlopen_side_effect(req, timeout=2):
            if isinstance(req, str):
                return _FakeHTTPResponse(200, {"status": "ok"})
            return _FakeHTTPResponse(200, {"content": "ok"})

        mock_urlopen.side_effect = _urlopen_side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            model = Path(tmp_dir) / "model.gguf"
            server = Path(tmp_dir) / "llama-server"
            model.write_text("x", encoding="utf-8")
            _make_executable(server)
            cfg = RunConfig(
                model_path=str(model),
                llama_server_bin=str(server),
                endpoint_mode=EndpointMode.COMPLETION,
                topology_mode=TopologyMode.SINGLE,
            )
            result = execute_single_smoke_with_receipt(cfg, output_dir=tmp_dir, intent="3b-smoke")
            receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))

        self.assertFalse(result.overall_verification_pass)
        self.assertEqual(receipt["controlled_shutdown_result"], "fail")

    @mock.patch("throughput_lab.execution_core.subprocess.check_output", return_value="abc123\n")
    @mock.patch("throughput_lab.runtime_service.subprocess.Popen")
    @mock.patch("throughput_lab.runtime_service.urllib.request.urlopen")
    def test_runtime_env_overlay_flows_to_launch(self, mock_urlopen, mock_popen, _mock_rev_parse):
        process = mock.Mock()
        process.wait.return_value = -15
        mock_popen.return_value = process

        def _urlopen_side_effect(req, timeout=2):
            if isinstance(req, str):
                return _FakeHTTPResponse(200, {"status": "ok"})
            return _FakeHTTPResponse(200, {"content": "ok"})

        mock_urlopen.side_effect = _urlopen_side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            model = Path(tmp_dir) / "model.gguf"
            server = Path(tmp_dir) / "llama-server"
            model.write_text("x", encoding="utf-8")
            _make_executable(server)
            cfg = RunConfig(
                model_path=str(model),
                llama_server_bin=str(server),
                endpoint_mode=EndpointMode.COMPLETION,
                topology_mode=TopologyMode.SINGLE,
                runtime_env={"CUDA_VISIBLE_DEVICES": "0"},
            )
            execute_single_smoke_with_receipt(cfg, output_dir=tmp_dir, intent="3b-smoke")

        _, kwargs = mock_popen.call_args
        self.assertEqual(kwargs["env"]["CUDA_VISIBLE_DEVICES"], "0")

    def test_invalid_contract_path_emits_structured_failure_receipt(self):
        cfg = RunConfig(
            model_path="/missing/model.gguf",
            llama_server_bin="/missing/llama-server",
            endpoint_mode=EndpointMode.CHAT_COMPLETIONS,
            request_model=None,
            topology_mode=TopologyMode.SINGLE,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = execute_single_smoke_with_receipt(cfg, output_dir=tmp_dir, intent="invalid-contract")
            receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
        self.assertFalse(result.overall_verification_pass)
        self.assertEqual(receipt["overall_verification_result"], "fail")
        self.assertIn("failure_summary", receipt)

    @mock.patch("throughput_lab.execution_core.subprocess.check_output", return_value="abc123\n")
    @mock.patch("throughput_lab.runtime_service.subprocess.Popen")
    @mock.patch("throughput_lab.runtime_service.urllib.request.urlopen")
    def test_semantic_fail_marks_overall_fail_even_with_clean_process(self, mock_urlopen, mock_popen, _mock_rev_parse):
        process = mock.Mock()
        process.wait.return_value = 0
        mock_popen.return_value = process

        def _urlopen_side_effect(req, timeout=2):
            if isinstance(req, str):
                return _FakeHTTPResponse(200, {"status": "ok"})
            return _FakeHTTPResponse(200, {"content": "unexpected"})

        mock_urlopen.side_effect = _urlopen_side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            model = Path(tmp_dir) / "model.gguf"
            server = Path(tmp_dir) / "llama-server"
            model.write_text("x", encoding="utf-8")
            _make_executable(server)

            cfg = RunConfig(
                model_path=str(model),
                llama_server_bin=str(server),
                endpoint_mode=EndpointMode.COMPLETION,
                topology_mode=TopologyMode.SINGLE,
                verification_mode=VerificationMode.EXACT,
                expected_text="expected",
            )
            result = execute_single_smoke_with_receipt(cfg, output_dir=tmp_dir, intent="3b-smoke")
            receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))

        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.overall_verification_pass)
        self.assertEqual(receipt["semantic_verification_result"], "fail")
        self.assertEqual(receipt["overall_verification_result"], "fail")


class CliBehaviorTests(unittest.TestCase):
    def test_single_smoke_cli_exits_nonzero_on_overall_fail(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = Path(tmp_dir) / "cfg.json"
            cfg = {
                "model_path": "/missing/model.gguf",
                "llama_server_bin": "/missing/llama-server",
                "endpoint_mode": "/completion",
                "topology_mode": "single",
                "verification_mode": "NON_EMPTY",
                "prompt": "hello",
            }
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_core_job.py",
                    "--config-json",
                    str(cfg_path),
                    "--single-smoke",
                    "--intent",
                    "cli-test",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
            )
        self.assertNotEqual(proc.returncode, 0)
        parsed = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(parsed["mode"], "single-smoke")
        self.assertEqual(parsed["status"], "failure")
        self.assertIn("timestamp_utc", parsed)

    def test_config_override_replaces_scalars_sequences_and_runtime_env(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir) / "base.json"
            override_path = Path(tmp_dir) / "override.json"
            base = {
                "model_path": "/base/model.gguf",
                "llama_server_bin": "/base/llama-server",
                "port": 18080,
                "topology_mode": "single",
                "endpoint_mode": "/completion",
                "verification_mode": "NON_EMPTY",
                "stop_tokens": ["</s>"],
                "extra_llama_server_args": ["--no-warmup"],
                "runtime_env": {"CUDA_VISIBLE_DEVICES": "0", "OMP_NUM_THREADS": "8"},
                "prompt": "hello",
            }
            override = {
                "model_path": "/override/model.gguf",
                "port": 19090,
                "stop_tokens": ["<|eot_id|>"],
                "extra_llama_server_args": ["--flash-attn"],
                "runtime_env": {"CUDA_VISIBLE_DEVICES": "1"},
            }
            base_path.write_text(json.dumps(base), encoding="utf-8")
            override_path.write_text(json.dumps(override), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_core_job.py",
                    "--config-json",
                    str(base_path),
                    "--config-override-json",
                    str(override_path),
                    "--dry-run",
                    "--intent",
                    "override-test",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
            )
        self.assertEqual(proc.returncode, 0)
        packet = json.loads(proc.stdout.decode("utf-8"))
        plan = packet["data"]["plan"]
        self.assertEqual(plan["resolved_model_path"], "/override/model.gguf")
        self.assertEqual(plan["resolved_command"][3:5], ["--port", "19090"])
        self.assertEqual(plan["resolved_request_payload"]["stop"], ["<|eot_id|>"])
        self.assertEqual(plan["resolved_runtime_env"], {"CUDA_VISIBLE_DEVICES": "1"})
        self.assertEqual(plan["config_snapshot"]["extra_llama_server_args"], ["--flash-attn"])

    def test_config_override_unknown_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir) / "base.json"
            override_path = Path(tmp_dir) / "override.json"
            base = {
                "model_path": "/base/model.gguf",
                "llama_server_bin": "/base/llama-server",
                "topology_mode": "single",
                "endpoint_mode": "/completion",
                "verification_mode": "NON_EMPTY",
            }
            override = {"not_a_real_field": 123}
            base_path.write_text(json.dumps(base), encoding="utf-8")
            override_path.write_text(json.dumps(override), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_core_job.py",
                    "--config-json",
                    str(base_path),
                    "--config-override-json",
                    str(override_path),
                    "--dry-run",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
            )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unknown override key", proc.stderr.decode("utf-8"))


class PreflightPacketTests(unittest.TestCase):
    def test_preflight_only_success_packet_shape(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            model = Path(tmp_dir) / "model.gguf"
            server = Path(tmp_dir) / "llama-server"
            model.write_text("x", encoding="utf-8")
            _make_executable(server)
            cfg = RunConfig(model_path=str(model), llama_server_bin=str(server), port=0)
            packet, code = preflight_packet(cfg, output_dir=tmp_dir, intent="preflight")
        self.assertEqual(code, 0)
        self.assertEqual(packet["mode"], "preflight-only")
        self.assertEqual(packet["status"], "success")
        self.assertIn("data", packet)
        self.assertIsNone(packet["receipt_path"])
        self.assertIn("config_snapshot", packet["data"])
        self.assertIn("resolved_command", packet["data"])
        self.assertIn("resolved_request_payload", packet["data"])

    def test_preflight_only_failure_packet_shape(self):
        cfg = RunConfig(model_path="/missing/model.gguf", llama_server_bin="/missing/llama-server")
        packet, code = preflight_packet(cfg, output_dir="/tmp", intent="preflight")
        self.assertEqual(code, 1)
        self.assertEqual(packet["mode"], "preflight-only")
        self.assertEqual(packet["status"], "failure")
        self.assertIsNone(packet["receipt_path"])


class PacketShapeTests(unittest.TestCase):
    def test_top_level_packet_fields_stable(self):
        cfg = RunConfig(model_path="/missing/model.gguf", llama_server_bin="/missing/llama-server")
        dry_packet, _ = dry_run_packet(cfg, output_dir="/tmp", intent="shape")
        preflight_pkt, _ = preflight_packet(cfg, output_dir="/tmp", intent="shape")
        self.assertEqual(set(dry_packet.keys()), set(preflight_pkt.keys()))

    def test_cli_single_smoke_envelope_matches_top_level_shape(self):
        expected_keys = {
            "packet_version",
            "mode",
            "status",
            "run_id",
            "timestamp_utc",
            "intent",
            "tool_name",
            "receipt_path",
            "failure_summary",
            "next_step",
            "data",
        }
        cfg = RunConfig(model_path="/missing/model.gguf", llama_server_bin="/missing/llama-server")
        dry_packet, _ = dry_run_packet(cfg, output_dir="/tmp", intent="shape")
        self.assertEqual(set(dry_packet.keys()), expected_keys)


class ProfileTests(unittest.TestCase):
    def test_first_profile_is_explicit_native_completion(self):
        cfg = json.loads(Path("configs/first_3b_single_smoke.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["endpoint_mode"], "/completion")
        self.assertEqual(cfg["verification_mode"], "NON_EMPTY")


if __name__ == "__main__":
    unittest.main()
