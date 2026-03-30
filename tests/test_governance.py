import unittest

from llama_nexus_lab.governance import load_agent_contracts, load_prompt_asset_manifests, manifest_by_asset_id, contract_by_agent_id


class GovernanceTests(unittest.TestCase):
    def test_prompt_assets_load(self):
        manifests = load_prompt_asset_manifests()
        self.assertGreaterEqual(len(manifests), 4)
        router = manifest_by_asset_id("router_system", manifests)
        self.assertEqual(router.kind, "prompt_config")

    def test_agent_contracts_load(self):
        contracts = load_agent_contracts()
        self.assertGreaterEqual(len(contracts), 4)
        router = contract_by_agent_id("router", contracts)
        self.assertTrue(router.receipt_required)


if __name__ == "__main__":
    unittest.main()
