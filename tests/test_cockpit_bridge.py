import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib import error, request

from scripts.run_nexus_cockpit_bridge import build_server
from scripts.validate_nexus_cockpit_contract import validate_payload, validate_receipt


class CockpitBridgeTests(unittest.TestCase):
    def _get_json(self, url: str) -> tuple[int, dict]:
        with request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _post_json(self, url: str, payload: dict) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_bridge_endpoints_and_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session = Path(td) / "session.json"
            receipts = Path(td) / "receipts"
            server = build_server("127.0.0.1", 0, session, receipts)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                code, health = self._get_json(base + "/healthz")
                self.assertEqual(code, 200)
                self.assertEqual(health["status"], "ok")

                code, capabilities = self._get_json(base + "/capabilities")
                self.assertEqual(code, 200)
                validate_payload("capabilities", capabilities)
                self.assertTrue(capabilities["local_only"])
                self.assertEqual(
                    capabilities["allowed_actions"],
                    ["generate_turn_packet", "load_preset", "preview", "show_recent_artifacts"],
                )

                code, action_specs = self._get_json(base + "/action-specs")
                self.assertEqual(code, 200)
                validate_payload("action_specs", action_specs)
                described = [row["action"] for row in action_specs["actions"]]
                self.assertEqual(described, ["load_preset", "preview", "show_recent_artifacts", "generate_turn_packet"])

                code, snapshot = self._get_json(base + "/snapshot")
                self.assertEqual(code, 200)
                validate_payload("snapshot", snapshot)

                code, action = self._post_json(base + "/action", {"action": "load_preset", "source": "library", "selection": "1", "topic": "bridge"})
                self.assertEqual(code, 200)
                validate_payload("result", action)

                receipt_path = Path(action["receipt_path"])
                self.assertTrue(receipt_path.exists())
                validate_receipt(json.loads(receipt_path.read_text(encoding="utf-8")))

                code, listing = self._get_json(base + "/receipts")
                self.assertEqual(code, 200)
                self.assertTrue(listing["receipts"])
                name = listing["receipts"][0]

                code, receipt_payload = self._get_json(base + "/receipts/" + name)
                self.assertEqual(code, 200)
                self.assertEqual(receipt_payload["action"], "load_preset")

                code, denied = self._post_json(base + "/action", {"action": "launch"})
                self.assertEqual(code, 403)
                self.assertEqual(denied["status"], "error")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
