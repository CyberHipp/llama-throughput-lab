# NEXUS Branch Publish Instructions

## Goal
Publish NEXUS automation and documentation updates from a clean branch with auditable evidence.

## Steps
1. Confirm clean working tree: `git status --short`.
2. Run validation checks used by this repository.
3. Review changed files for sensitive content (`logs/`, inbox extracts, credentials).
4. Commit with bounded scope and descriptive message.
5. Push branch and open PR with:
   - change summary
   - risk assessment
   - validation evidence
6. After merge, verify expected artifacts and monitoring signals.

## Guardrails
- Never commit generated runtime logs.
- Keep operational docs and automation scaffolding in separate commits when practical.
