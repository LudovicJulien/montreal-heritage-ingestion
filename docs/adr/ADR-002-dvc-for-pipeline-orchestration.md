# ADR-002: Use DVC for Data Pipeline Orchestration and Versioning

**Status:** Accepted  
**Date:** 2026-06-25

## Context

The pipeline produces binary artifacts (Parquet, JSONL) that must be reproducible, versioned alongside code, and re-runnable without re-executing unchanged stages. Alternatives considered: raw Bash scripts with manual file management (rejected — no dependency graph, no caching), Git LFS for data files (rejected — LFS does not understand stage dependencies or skip-if-unchanged logic), and Airflow (rejected — operational overhead far exceeds the complexity of a linear 4-stage batch pipeline).

## Decision

Use DVC with a `dvc.yaml` pipeline definition to declare the four stages, their dependencies, and their outputs. Data artifacts are stored outside Git (`.gitignore`) and tracked via `dvc.lock`.

## Rationale

DVC's `dvc repro` resolves the dependency graph and skips stages whose inputs have not changed, which aligns naturally with the SHA-256 idempotence already built into the ingest stage. `dvc.lock` pins exact content hashes of every artifact, making any past pipeline run reproducible with `dvc checkout`. The local remote is sufficient for a single-developer project; switching to S3 later requires only a config change.

## Consequences

- `data/` is git-ignored; collaborators must run `dvc pull` before `dvc repro`.
- `dvc.lock` must be committed alongside every code change that alters an artifact.
- DVC adds a dependency that contributors must install (`pip install dvc`).
