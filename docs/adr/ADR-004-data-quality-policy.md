# ADR-004: Data Quality Policy — Reject, Nullify, or Normalize

**Status:** Accepted
**Date:** 2026-08-07

## Context

Stages 01 and 02 are deliberately non-destructive: ingest preserves the CSV as-is, and clean
normalizes text without imputing or dropping anything. Stage 03 is the first stage that is allowed
to *change the meaning* of a record, and it therefore needs a rule for what to do when a value
violates a constraint.

Without an explicit rule the choice gets made implicitly, function by function, and the current
stubs already disagree with each other: `_cast_years` says invalid years are *nullified*, while
`_validate_arrondissement` says non-conforming boroughs cause the *row to be rejected*. Applied to
the real data, that inconsistency is expensive — see the profile in
[docs/pipeline/03-normalize.md](../pipeline/03-normalize.md):

- 242 rows (18 %) carry `fin_des_travaux = 0`, a sentinel meaning "unknown".
- 30 rows belong to **villes liées** — independent municipalities of the Montreal agglomeration
  (Westmount, Dorval, Senneville…) that are not among the 19 boroughs, but whose buildings are
  perfectly valid heritage records.
- 1306 rows fail borough matching for purely typographic reasons — a suffix, an em dash, and an
  apostrophe that stage 02 itself introduces.

A reject-first policy would discard between 18 % and 98 % of the corpus depending on which
constraint fires, and would do so to encode facts the source already states plainly.

Three options are available for any given violation:

| Option | Meaning |
|---|---|
| **Normalize** | The value is correct but written in a non-canonical form; rewrite it. |
| **Nullify** | The value is genuinely absent or meaningless; replace it with null and keep the row. |
| **Reject** | The record cannot be identified or located at all; drop the row and log it. |

## Decision

**Nullify the field, not the record. Reject only when the record cannot be identified.**

The pipeline preserves rows by default. A constraint violation degrades a single field to null; it
never removes a building from the corpus unless the record has no usable identity.

Applied column by column for stage 03:

| Column | Violation | Policy |
|---|---|---|
| `arrondissement` | suffix `" (Montréal)"`, em dash U+2014, curly apostrophe U+2019 | **Normalize** before any comparison |
| `arrondissement` | value is a ville liée, not one of the 19 boroughs | **Keep**, tagged (see below) |
| `arrondissement` | value matches neither a borough nor a known ville liée | **Nullify**, log at `WARNING` |
| `type_de_voie` | non-canonical case (`Avenue` → `avenue`) | **Normalize** (lowercase) |
| `est_ouest` | abbreviated form (`E` → `Est`) | **Normalize** — absent from this extract, kept as a guard |
| `debut_des_travaux` / `fin_des_travaux` | sentinel `0` or `9999`, or outside `[1600, 2030]` | **Nullify** — never clamp |
| `centro_x` / `centro_y` | outside the Montreal bounding box | **Nullify both**, log at `WARNING` |
| `nom_historique`, `voie` | null | **Keep** — schema relaxed to `nullable=True` |
| `identifiant_batiment` | null | **Reject the row**, log at `ERROR` |

A `municipalite_type` column is added to the stage 03 output, taking the value `arrondissement`
(1306 rows) or `ville_liee` (30 rows). This keeps the agglomeration data in the corpus while
letting any downstream consumer filter to the Ville de Montréal proper with a single predicate.

**Assumption made in the absence of an explicit scope statement:** the dataset covers the *Montreal
agglomeration*, not strictly the Ville de Montréal. If the intended scope is the 19 boroughs only,
this ADR is superseded and the `municipalite_type` column becomes a filter rather than a tag — a
one-line change, which is precisely why the distinction is materialized as data rather than baked
into a drop.

## Rationale

**Nullifying preserves the only information the source actually provides.** `fin_des_travaux = 0`
is not corrupt data; it is the publisher's way of writing "unknown", and null is the faithful
translation. Clamping it to `2030` — which the current `_cast_years` docstring implies — would
fabricate a construction date that no source supports, and it would be indistinguishable from a
real 2030 date downstream. Fabrication is strictly worse than absence in a RAG corpus, where a
wrong date is retrieved and quoted with the same confidence as a right one.

**Rejecting rows is reserved for records that cannot be addressed.** A building with no
`identifiant_batiment` cannot be deduplicated, cannot be traced back to the source, and cannot be
referenced by a retrieval answer; it has no identity to preserve. Everything else — a missing name,
a missing street, an unknown end date — still describes a real building at a real location, and is
worth retrieving.

**Normalization is not validation.** The borough case makes this concrete: all three mismatch
causes are typographic, and one of them is introduced by our own stage 02. Treating a typographic
variant as a validation failure would have deleted 98 % of the corpus while the data was entirely
correct. Comparison must therefore always happen on a canonical form, and the canonical form must
be computed at comparison time rather than assumed to arrive intact from an upstream stage.

**Tagging beats filtering for scope decisions.** Whether villes liées belong in the corpus is a
product question, not a data quality one. Encoding the answer as a dropped row destroys the
information; encoding it as a column defers the choice to whoever consumes the output, at no cost.

**Every degradation is logged and counted.** A silent nullification is indistinguishable from
source data that was already null, which makes quality regressions after a data refresh invisible.
Stage 03 emits a per-column count of nullified values, in the same structured-log style as the
existing `Converted {n} empty strings to null` in stage 02.

## Consequences

- `NormalizedSchema` must relax `nom_historique` and `voie` to `nullable=True`. Only
  `arrondissement` (0 nulls on 1336) and `identifiant_batiment` (non-null by construction, after
  rejection) remain required.
- The output gains a `municipalite_type` column; `NormalizedSchema` and `BuildingEnriched` both
  need to carry it if the distinction is to reach the RAG engine.
- Row count is not preserved across stage 03: exactly 1 row is dropped on the current extract. This
  breaks the naive `test_output_record_count_matches_input` assertion sketched in
  `tests/integration/test_pipeline_e2e.py` — the invariant to assert is
  `output == input − rejected`, with `rejected` logged.
- Nullification widens null rates downstream: `fin_des_travaux` goes from 49.9 % to 68.0 % null,
  and `debut_des_travaux` from 24.0 % to 25.6 %. Stage 04 must treat both as routinely absent when
  composing `BuildingEnriched.text`.
- The `lambert_to_wgs84()` stub in `utils/geo.py` and the CRS question in `schemas.py` are resolved
  as unnecessary: the source is already WGS84. Both can be deleted rather than implemented.
- `MONTREAL_ARRONDISSEMENTS` stays as the canonical reference and is **not** edited to match the
  source's typography. A separate normalization function maps incoming values onto it, so the
  constant keeps documenting the official names rather than this extract's quirks.
- A companion `MONTREAL_VILLES_LIEES` constant is required in `utils/geo.py` to distinguish a known
  ville liée from a genuinely unrecognized value — without it, the third `arrondissement` rule
  (nullify the unknown) cannot be expressed.
