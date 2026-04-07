import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from llama_nexus_lab.config_loader import load_nexus_config
from llama_nexus_lab.pipeline import run_research_pipeline, write_pipeline_artifacts
from llama_nexus_lab.router import expand_intents, select_model


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
                reasoner_adapter=cfg.runtime.reasoner_adapter,
            )
            cfg = cfg.__class__(
                search=cfg.search,
                pipeline=cfg.pipeline,
                runtime=patched,
                router_rules=cfg.router_rules,
                model_profiles=cfg.model_profiles,
            )
            result = run_research_pipeline("nexus architecture", cfg)
            paths = write_pipeline_artifacts(result, cfg.runtime.artifacts_dir)
            self.assertTrue(Path(paths["answer_path"]).exists())
            self.assertTrue(Path(paths["trace_path"]).exists())
            receipt = json.loads(Path(paths["receipt_path"]).read_text(encoding="utf-8"))
            self.assertEqual(receipt["run_id"], result.run_id)
            self.assertIn("verification_pass", receipt)
            stages = [row["stage"] for row in receipt["receipts"]]
            self.assertIn("verify", stages)

    def test_live_reasoner_adapter_success_updates_reason_receipt(self):
        cfg = load_nexus_config("configs/nexus/default.json")
        patched_pipeline = cfg.pipeline.__class__(
            run_id_prefix=cfg.pipeline.run_id_prefix,
            max_search_intents=cfg.pipeline.max_search_intents,
            max_iterations=cfg.pipeline.max_iterations,
            retrieval_chunk_size=cfg.pipeline.retrieval_chunk_size,
            retrieval_top_k=cfg.pipeline.retrieval_top_k,
            cache_ttl_s=cfg.pipeline.cache_ttl_s,
            strict_citation_required=cfg.pipeline.strict_citation_required,
            dry_run=False,
        )
        patched_runtime = cfg.runtime.__class__(
            artifacts_dir=cfg.runtime.artifacts_dir,
            retry_attempts=cfg.runtime.retry_attempts,
            retry_backoff_s=cfg.runtime.retry_backoff_s,
            stage_timeout_s=cfg.runtime.stage_timeout_s,
            reasoner_adapter=cfg.runtime.reasoner_adapter.__class__(
                enabled=True,
                base_url="http://adapter.local",
                model="fake-reasoner",
                timeout_s=5,
            ),
        )
        cfg = cfg.__class__(
            search=cfg.search,
            pipeline=patched_pipeline,
            runtime=patched_runtime,
            router_rules=cfg.router_rules,
            model_profiles=cfg.model_profiles,
        )
        fake_response = mock.MagicMock()
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False
        fake_response.status = 200
        fake_response.read.return_value = b'{"choices":[{"message":{"content":"live adapter answer"}}]}'
        with mock.patch("llama_nexus_lab.pipeline._search_intent", return_value=[]):
            with mock.patch("llama_nexus_lab.pipeline.urllib.request.urlopen", return_value=fake_response):
                result = run_research_pipeline("nexus architecture", cfg)
        reason_stage = [row for row in result.receipts if row.stage.value == "reason"][0]
        self.assertEqual(reason_stage.status, "pass")
        self.assertTrue(reason_stage.details["adapter_used"])
        self.assertEqual(reason_stage.details["adapter_model"], "fake-reasoner")
        self.assertIn("live adapter answer", result.answer)

    def test_live_reasoner_adapter_failure_fails_closed(self):
        cfg = load_nexus_config("configs/nexus/default.json")
        patched_pipeline = cfg.pipeline.__class__(
            run_id_prefix=cfg.pipeline.run_id_prefix,
            max_search_intents=cfg.pipeline.max_search_intents,
            max_iterations=cfg.pipeline.max_iterations,
            retrieval_chunk_size=cfg.pipeline.retrieval_chunk_size,
            retrieval_top_k=cfg.pipeline.retrieval_top_k,
            cache_ttl_s=cfg.pipeline.cache_ttl_s,
            strict_citation_required=cfg.pipeline.strict_citation_required,
            dry_run=False,
        )
        patched_runtime = cfg.runtime.__class__(
            artifacts_dir=cfg.runtime.artifacts_dir,
            retry_attempts=cfg.runtime.retry_attempts,
            retry_backoff_s=cfg.runtime.retry_backoff_s,
            stage_timeout_s=cfg.runtime.stage_timeout_s,
            reasoner_adapter=cfg.runtime.reasoner_adapter.__class__(
                enabled=True,
                base_url="http://adapter.local",
                model="fake-reasoner",
                timeout_s=5,
            ),
        )
        cfg = cfg.__class__(
            search=cfg.search,
            pipeline=patched_pipeline,
            runtime=patched_runtime,
            router_rules=cfg.router_rules,
            model_profiles=cfg.model_profiles,
        )
        with mock.patch("llama_nexus_lab.pipeline._search_intent", return_value=[]):
            with mock.patch("llama_nexus_lab.pipeline.urllib.request.urlopen", side_effect=TimeoutError("timed out")):
                with self.assertRaises(RuntimeError) as ctx:
                    run_research_pipeline("nexus architecture", cfg)
        self.assertIn("reason_stage_timeout", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
