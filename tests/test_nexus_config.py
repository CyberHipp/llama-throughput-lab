import unittest

from llama_nexus_lab.config_loader import load_nexus_config


class NexusConfigTests(unittest.TestCase):
    def test_load_json_config(self):
        cfg = load_nexus_config("configs/nexus/default.json")
        self.assertEqual(cfg.pipeline.run_id_prefix, "nexus")
        self.assertTrue(cfg.pipeline.strict_citation_required)
        self.assertEqual(cfg.search.max_results_per_intent, 5)

    def test_yaml_without_dependency_fails_closed(self):
        with self.assertRaises(ValueError):
            load_nexus_config("configs/nexus/default.yaml")


if __name__ == "__main__":
    unittest.main()
