# NEXUS Cockpit Bridge (local-only, pre-mobile seam)

## Purpose

`run_nexus_cockpit_bridge.py` provides a thin local HTTP JSON seam over existing Cockpit v2 machine-readable surfaces. It is the current pre-SymbiOS-Mobile integration surface for local clients that should not parse terminal output.

## Localhost-only posture

The bridge defaults to:

- host: `127.0.0.1`
- port: `8765`

This pass is intentionally local-only. No TLS, reverse-proxy, public network exposure, or auth redesign is included.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Basic bridge status. |
| `GET` | `/capabilities` | Bridge discoverability payload (local-only posture, actions, endpoints, contract versions). |
| `GET` | `/action-specs` | Per-action payload contract for currently allowed bridge actions. |
| `GET` | `/snapshot` | Returns Cockpit snapshot contract payload. |
| `POST` | `/action` | Executes one allowed cockpit action and returns action-result envelope. |
| `GET` | `/receipts` | Lists recent receipt filenames from configured receipts dir. |
| `GET` | `/receipts/<name>` | Returns one receipt JSON from configured receipts dir only. |

## Allowed actions (this pass)

| Action | Allowed |
|---|---|
| `load_preset` | ✅ |
| `preview` | ✅ |
| `show_recent_artifacts` | ✅ |
| `generate_turn_packet` | ✅ |
| `launch` | ❌ |
| `enqueue` | ❌ |
| `run_queue` | ❌ |
| `reset_queue` | ❌ |
| Unknown actions | ❌ |

## Example curl usage

Start bridge:

```bash
python3 scripts/run_nexus_cockpit_bridge.py --host 127.0.0.1 --port 8765
```

Health:

```bash
curl -s http://127.0.0.1:8765/healthz
```

Capabilities:

```bash
curl -s http://127.0.0.1:8765/capabilities
```

Action specs:

```bash
curl -s http://127.0.0.1:8765/action-specs
```

Snapshot:

```bash
curl -s http://127.0.0.1:8765/snapshot
```

Action:

```bash
curl -s -X POST http://127.0.0.1:8765/action \
  -H 'Content-Type: application/json' \
  -d '{"action":"load_preset","source":"library","selection":"1","topic":"bridge demo"}'
```

Receipts list:

```bash
curl -s http://127.0.0.1:8765/receipts
```

Receipt fetch:

```bash
curl -s http://127.0.0.1:8765/receipts/<receipt-file-name>.json
```

## Contract relationship

- Contract schemas + validator: `docs/nexus_cockpit_contract.md`
- CLI contract smoke harness: `docs/nexus_cockpit_contract_smoke.md`
- Bridge smoke harness: `scripts/run_nexus_cockpit_bridge_smoke.py`

The bridge smoke harness proves the HTTP seam end-to-end while reusing the same cockpit validator.
