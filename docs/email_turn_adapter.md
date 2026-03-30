# Email turn adapter (protocol only)

`llama_nexus_lab/email_turn_adapter.py` implements a transport-agnostic turn packet protocol.

Protocol version:
- `email-turn-v1`

Required fields:
- `protocol`
- `game_type`
- `game_id`
- `turn`
- `actor`
- `move`
- `state`
- `legal_next`
- `ts_utc`
- `idempotency_key`
- `hash`

## Supported workflow

- Build packet (`build_turn_packet`)
- Validate packet (`validate_turn_packet`)
- Serialize/load packet JSON
- Build outbound email bundle payload with:
  - plain-text summary
  - html summary
  - attachment path (`turn_packet_v1.json`)

## Non-goals

- No live Gmail/SMTP sending in required path.
- No JavaScript execution in email clients.
- No chess engine implementation.
