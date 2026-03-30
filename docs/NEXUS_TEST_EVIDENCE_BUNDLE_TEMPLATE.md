# NEXUS Test Evidence Bundle Template

Attach this bundle (or its equivalent) to PRs affecting NEXUS.

## PR metadata
- PR / branch:
- candidate SHA:
- base SHA:
- reviewer:

## Commands run
```bash
make ci
python3 -m unittest tests/test_execution_core.py tests/test_nexus_config.py tests/test_nexus_pipeline.py
python3 scripts/security_check.py
python3 scripts/run_nexus_pipeline.py --query "nexus smoke" --config configs/nexus/default.json
```

## Results summary
- make ci:
- unit tests:
- security check:
- sample nexus run:

## Artifact paths
- answer path:
- receipt path:
- evidence path:

## Receipt highlights
- run_id:
- confidence:
- stages present:
- degraded/fail classification (if any):

## Contract checks
- [ ] existing throughput contract unchanged or versioned
- [ ] nexus artifact contract documented
- [ ] docs/examples match actual behavior

## Risk notes
-

## Reviewer sign-off
- [ ] evidence sufficient for merge decision

