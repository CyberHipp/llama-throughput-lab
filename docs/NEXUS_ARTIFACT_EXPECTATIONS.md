# NEXUS Artifact Expectations

When the nexus lane is functioning correctly, each bounded run should produce at least:

## Required artifacts
- answer markdown
- receipt JSON
- evidence JSON

## Receipt minimum fields
- run_id
- query
- status / overall result
- confidence
- stage receipts
- degraded/failure classification when applicable
- artifact paths

## Evidence minimum fields
- intent
- title
- url
- snippet
- content hash

## Answer minimum qualities
- states evidence count
- contains citations or explicit missing-evidence note
- includes confidence level
- avoids overclaiming

## Acceptance note
A run that produces files but hides degraded retrieval or unsupported claims is not considered passing-quality.
