# ADR-001: Four-Stage Pipeline Architecture (Ingest → Clean → Normalize → Enrich)

**Status:** Accepted  
**Date:** 2026-06-25

## Context

The pipeline processes 2,742 heritage buildings from a single source CSV into RAG-ready enriched records. An early prototype used one monolithic script, which made it hard to test individual transformations, difficult to rerun partial work after a failure, and impossible to inspect intermediate data quality issues.

## Decision

Split the pipeline into four sequential stages with a Parquet (or JSONL) artifact written at each boundary: `s01_ingest`, `s02_clean`, `s03_normalize`, and `s04_enrich`.

## Rationale

Each stage has a single, clearly scoped responsibility: raw CSV preservation, text normalisation, type-casting and geo-validation, and NER enrichment respectively. Pandera schemas enforced at each stage boundary make contract violations explicit and catchable early. Each stage can be unit-tested in isolation with a minimal fixture DataFrame, without needing the full source CSV. Debugging a data quality issue reduces to inspecting the Parquet at the failing boundary rather than tracing through a 500-line script.

## Consequences

- DVC tracks four intermediate artifacts (`01_raw`, `02_clean`, `03_normalized`, `04_enriched`); re-running only the affected downstream stages on a source change is free.
- Four Pandera schemas must be maintained and kept in sync with stage outputs.
- Slight I/O overhead from writing intermediate Parquet files (~negligible for 2.7k rows).
