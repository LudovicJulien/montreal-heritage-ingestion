# Architecture Decision Records

This directory documents the key architectural choices made in the Montreal Heritage Ingestion pipeline. Each ADR captures a decision in context — what we chose, why, and what it costs.

## How to Read ADRs

Each record follows the same four-section structure:

| Section | What it answers |
|---------|----------------|
| **Context** | What problem or constraint forced a decision |
| **Decision** | The specific choice made |
| **Rationale** | Why this option over the alternatives |
| **Consequences** | Trade-offs accepted — positive and negative |

ADRs are immutable once accepted. Superseded decisions get a new ADR that references the old one; the original is kept for historical context.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-four-stage-pipeline-architecture.md) | Four-Stage Pipeline Architecture (Ingest → Clean → Normalize → Enrich) | Accepted |
| [ADR-002](ADR-002-dvc-for-pipeline-orchestration.md) | Use DVC for Pipeline Orchestration and Versioning | Accepted |
| [ADR-003](ADR-003-sha256-row-hashing-for-idempotence.md) | Use SHA-256 Hashing for Row-Level Idempotence | Accepted |
