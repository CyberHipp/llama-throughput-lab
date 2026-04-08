import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class CockpitBridgeSmokeTests(unittest.TestCase):
    def test_bridge_smoke_harness_produces_validated_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cmd = [
                "python3",
                "scripts/run_nexus_cockpit_bridge_smoke.py",
                "--artifact-root",
                td,
                "--run-id",
                "bridge-smoke-test",
            ]
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)

            summary = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(summary["status"], "ok")
            run_dir = Path(summary["artifact_dir"])

            expected = [
                "healthz.json",
                "capabilities.json",
                "snapshot.json",
                "action_result.json",
                "receipts.json",
                "receipt.json",
                "validate_capabilities.json",
                "validate_snapshot.json",
                "validate_result.json",
                "validate_receipt.json",
                "summary.json",
            ]
            for name in expected:
                self.assertTrue((run_dir / name).exists(), msg=f"missing {name}")

            for name in (
                "validate_capabilities.json",
                "validate_snapshot.json",
                "validate_result.json",
                "validate_receipt.json",
            ):
                payload = json.loads((run_dir / name).read_text(encoding="utf-8"))
                self.assertEqual(payload.get("status"), "ok")

            action_result = json.loads((run_dir / "action_result.json").read_text(encoding="utf-8"))
            receipt_payload = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))
            self.assertTrue(Path(action_result["receipt_path"]).exists())
            self.assertEqual(receipt_payload["action"], "load_preset")


if __name__ == "__main__":
    unittest.main()
