# ADR-003: Use SHA-256 Hashing for Row-Level Idempotence

**Status:** Accepted  
**Date:** 2026-06-25

## Context

The source CSV is updated periodically by Données Québec. Re-running the full pipeline on every update would reprocess thousands of unchanged records, inflating NER costs and downstream processing time. A mechanism is needed to detect which records have actually changed between runs.

## Decision

Compute a SHA-256 hash of each row's raw field values at the end of the ingest stage and store it as a `record_hash` column (64-char hex string). On subsequent runs, rows whose hash already appears in the previous output Parquet are skipped.

## Rationale

SHA-256 is deterministic across runs and platforms, making it safe to compare across executions without ordering concerns. The operation is O(n) and completes in well under a second on 2,742 rows. Collision probability on a dataset this size is negligible (~10⁻⁶⁸). Hashing the raw source columns only — before any pipeline metadata columns are appended — ensures `record_hash` reflects the actual source content, not incidental metadata changes.

## Consequences

- Each row gains a 64-byte `record_hash` column (~0.17 MB total overhead on 2.7k rows).
- Estimated pipeline re-run overhead: +5% on the ingest stage; all downstream stages see fewer rows on incremental updates.
- The `record_hash` column must be present in `RawSchema`; downstream schemas may propagate it for lineage tracing.
- A row with any field changed — even whitespace — produces a new hash and is re-processed in full.
