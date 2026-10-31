# ADR-007: Export Provenance Fields and a Deterministic exported_at

**Status:** Accepted
**Date:** 2026-10-31

## Context

The front-end shows how fresh the data is. `stats.json` carried no provenance, so the site had
nothing to display. Two fields are needed: the date the source dataset was last updated, and the
date the export was produced.

`stats.json` is a declared output of the `s06_export` DVC stage. An `exported_at` taken from
`datetime.now()` would rewrite the file on every `dvc repro --force` and change its hash, which
invalidates the DVC cache for anything downstream and makes two runs on identical inputs disagree.

## Decision

`stats.json` gains two keys, appended after the existing ones. No key is renamed or removed.

- `source_updated_at`: the Données Montréal portal's `last_modified` for the source resource,
  ISO 8601 UTC (`2025-06-19T14:26:38Z`), or `null` when unknown. `make download` writes it to
  `rawData/source_metadata.json` from the portal's CKAN `resource_show` API call. That is one
  metadata request, not a page fetch, so ADR-006 is unaffected. Stage 06 reads the sidecar, and
  the sidecar is a declared dependency of the stage in `dvc.yaml`.
- `exported_at`: the latest `ingested_at` in the merged corpus, same format, or `null` when the
  column is absent. It is not the wall clock. `ingested_at` is stamped by stage 01 and stored in
  DVC-tracked Parquet, so it changes only when the data is re-ingested.

A missing, malformed or unparsable sidecar gives `source_updated_at: null` and a logged warning.
The export does not fail on it, and no date is guessed.

## Consequences

- Re-running stage 06 on unchanged inputs produces a byte-identical `stats.json`. A test checks it.
- `exported_at` means "when this data was last ingested", not "when the file was written". For a
  front-end freshness label this is the more useful date, but the name is looser than the value.
- `dvc.yaml` now requires `rawData/source_metadata.json`. A fresh checkout must run
  `make download` before `dvc repro`.
- Fields not in the Zod schema the site validates against would fail a strict parse. Additive keys
  are only safe if that schema is updated first or is not strict about unknown keys. The site repo has no such schema yet (checked), so nothing blocks this today.
