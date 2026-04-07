import json
import tempfile
import unittest
from pathlib import Path

from llama_nexus_lab.gauntlet import QueueItem, process_queue, write_queue_manifest


class NexusQueueTests(unittest.TestCase):
    def test_queue_manifest_and_receipt_generation(self):
        items = [
            QueueItem("g1", "a.json", ("python", "a.py")),
            QueueItem("g2", "b.json", ("python", "b.py")),
        ]

        def _runner(_item: QueueItem):
            return {"run_id": "r1", "exit_code": 0, "artifacts": {"receipt": "ok.json"}}

        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest = write_queue_manifest(
                Path(tmp_dir) / "q.json",
                queue_id="queue-1",
                stop_on_fail=False,
                items=items,
            )
            receipt = process_queue(
                queue_items=items,
                stop_on_fail=False,
                run_item=_runner,
                receipt_path=Path(tmp_dir) / "q_receipt.json",
                queue_id="queue-1",
            )
            manifest_payload = json.loads(Path(manifest).read_text(encoding="utf-8"))
            receipt_payload = json.loads(Path(receipt).read_text(encoding="utf-8"))

        self.assertEqual(manifest_payload["queue_id"], "queue-1")
        self.assertEqual(len(receipt_payload["items"]), 2)
        self.assertEqual(receipt_payload["result"], "pass")

    def test_queue_stop_on_fail(self):
        items = [
            QueueItem("g1", "a.json", ("python", "a.py")),
            QueueItem("g2", "b.json", ("python", "b.py")),
        ]

        def _runner(item: QueueItem):
            if item.gauntlet_name == "g1":
                return {"run_id": "r-fail", "exit_code": 1, "reason": "boom", "artifacts": None}
            return {"run_id": "r-pass", "exit_code": 0, "artifacts": {}}

        with tempfile.TemporaryDirectory() as tmp_dir:
            receipt = process_queue(
                queue_items=items,
                stop_on_fail=True,
                run_item=_runner,
                receipt_path=Path(tmp_dir) / "q_receipt.json",
                queue_id="queue-2",
            )
            payload = json.loads(Path(receipt).read_text(encoding="utf-8"))

        self.assertEqual(payload["result"], "fail")
        self.assertEqual(payload["items"][0]["status"], "fail")
        self.assertEqual(payload["items"][1]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
