import json
import tempfile
import unittest
from pathlib import Path

from llama_nexus_lab.config_loader import load_nexus_config
from llama_nexus_lab.pipeline import run_research_pipeline, write_pipeline_artifacts
from llama_nexus_lab.router import expand_intents, select_model
from llama_nexus_lab.runtime import build_run_envelope


class NexusPipelineTests(unittest.TestCase):
    def test_expand_intents_is_bounded(self):
        intents = expand_intents("optimize llama serving with retrieval and critique", max_intents=4)
        self.assertLessEqual(len(intents), 4)
        self.assertGreaterEqual(len(intents), 1)

    def test_router_selects_expected_model(self):
        cfg = load_nexus_config("configs/nexus/default.json")
        model = select_model("reason", cfg)
        self.assertEqual(model.name, "nemotron-cascade-2-30b")

    def test_dry_run_pipeline_writes_artifacts(self):
        cfg = load_nexus_config("configs/nexus/default.json")
        with tempfile.TemporaryDirectory() as tmp_dir:
            patched = cfg.runtime.__class__(
                artifacts_dir=tmp_dir,
                retry_attempts=cfg.runtime.retry_attempts,
                retry_backoff_s=cfg.runtime.retry_backoff_s,
                stage_timeout_s=cfg.runtime.stage_timeout_s,
            )
            cfg = cfg.__class__(
                search=cfg.search,
                pipeline=cfg.pipeline,
                runtime=patched,
                router_rules=cfg.router_rules,
                model_profiles=cfg.model_profiles,
            )
            envelope = build_run_envelope(user_text="nexus architecture", metadata={"mode": "test"})
            result = run_research_pipeline("nexus architecture", cfg, envelope=envelope)
            paths = write_pipeline_artifacts(result, cfg.runtime.artifacts_dir)
            self.assertTrue(Path(paths["answer_path"]).exists())
            receipt = json.loads(Path(paths["receipt_path"]).read_text(encoding="utf-8"))
            self.assertEqual(receipt["run_id"], result.run_id)
            self.assertEqual(receipt["request_id"], result.request_id)
            self.assertIn("trace_id", receipt["receipts"][0])


if __name__ == "__main__":
    unittest.main()
