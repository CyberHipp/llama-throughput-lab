import os
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tools.automation.runtime_state import resolve_runtime_registry_path


class AutomationRuntimeStateTests(unittest.TestCase):
    def test_runtime_registry_path_resolution_uses_artifacts_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed = root / "registries/EMAIL_CONTROL_WATCHDOG_LEDGER_v1.tsv"
            seed.parent.mkdir(parents=True, exist_ok=True)
            seed.write_text("h1\th2\nseed\t1\n", encoding="utf-8")

            env = os.environ.copy()
            env["AUTOMATION_ROOT_DIR"] = str(root)
            with mock.patch.dict(os.environ, env, clear=False):
                runtime_path = resolve_runtime_registry_path("registries/EMAIL_CONTROL_WATCHDOG_LEDGER_v1.tsv")

            self.assertEqual(
                runtime_path,
                root / "artifacts" / "automation_state" / "registries/EMAIL_CONTROL_WATCHDOG_LEDGER_v1.tsv",
            )

    def test_seed_copied_to_runtime_state_on_first_use(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed = root / "registries/VORTEX_POST_QUEUE_AUGMENTATION_TASKS.tsv"
            seed.parent.mkdir(parents=True, exist_ok=True)
            body = "task_id\tpriority\tstate\nq1\thigh\tqueued\n"
            seed.write_text(body, encoding="utf-8")

            with mock.patch.dict(os.environ, {"AUTOMATION_ROOT_DIR": str(root)}, clear=False):
                runtime_path = resolve_runtime_registry_path("registries/VORTEX_POST_QUEUE_AUGMENTATION_TASKS.tsv")

            self.assertTrue(runtime_path.exists())
            self.assertEqual(runtime_path.read_text(encoding="utf-8"), body)

    def test_watchdog_writes_runtime_state_not_tracked_seed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed = root / "registries/EMAIL_CONTROL_WATCHDOG_LEDGER_v1.tsv"
            seed.parent.mkdir(parents=True, exist_ok=True)
            seed_contents = "run_id\tutc_timestamp\tcontroller\tstatus\tnotes\nseed\tt\tc\tok\tn\n"
            seed.write_text(seed_contents, encoding="utf-8")

            runtime_dir = root / "artifacts" / "automation_state"
            script = Path("tools/automation/gmail_control_watchdog.sh").resolve()
            result = subprocess.run(
                [str(script)],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "AUTOMATION_ROOT_DIR": str(root), "AUTOMATION_STATE_DIR": str(runtime_dir)},
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            runtime_ledger = runtime_dir / "registries/EMAIL_CONTROL_WATCHDOG_LEDGER_v1.tsv"
            self.assertTrue(runtime_ledger.exists())
            self.assertEqual(seed.read_text(encoding="utf-8"), seed_contents)
            self.assertGreater(len(runtime_ledger.read_text(encoding="utf-8").splitlines()), len(seed_contents.splitlines()))


if __name__ == "__main__":
    unittest.main()
