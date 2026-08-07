# Stage 03 — `s03_normalize.py`

> **Status: specification.** This stage is not implemented yet. This document profiles the data
> the stage will actually receive and fixes the contract it must honour. The function-by-function
> walkthrough — like [01 — Ingest](01-ingest.md) and [02 — Clean](02-clean.md) — is written after
> implementation, from real before/after values.

For the quality policy this stage applies (reject / nullify / normalize), see
[ADR-004](../adr/ADR-004-data-quality-policy.md).

Previous stage: [02 — Clean](02-clean.md).

---

**Input**: `data/02_clean/buildings_clean.parquet` — 1336 rows × 20 columns
**Output**: `data/03_normalized/buildings_normalized.parquet`

The critical point: this stage reads **the output of stage 02, not the source CSV**. Stage 02
rewrites text before stage 03 ever sees it, and one of those rewrites actively breaks borough
matching (see §2). Every figure below was measured on `buildings_clean.parquet`.

---

## 1. What the data actually contains

### Record count: 1336, not 2742

The source CSV spans **2743 physical lines** but holds **1336 records**. The arithmetic is exact:

```
1336 records + 1406 embedded newlines + 1 header = 2743 lines
```

**272 of the 1336 buildings** carry a multi-paragraph `HISTORIQUE_SOMMAIRE`, quoted and spanning
several lines each. A well-formed CSV is not a line-per-record format, so `wc -l` minus the header
yields 2742 — a figure that circulated through the README and two ADRs before being traced back
here. Only a quote-aware parser gives the right count, which `pandas.read_csv` has done correctly
since stage 01: the pipeline was never affected, only the prose.

The same embedded newlines are what `_collapse_whitespace` flattens in
[stage 02](02-clean.md#3-_collapse_whitespace-all-text-columns).

### Null rates

After stage 02, on 1336 rows:

| Column | Nulls | % | Note |
|---|---:|---:|---|
| `identifiant_batiment` | 1 | 0.1 % | intended as the primary key — see §6 |
| `nom_historique` | 30 | 2.2 % | |
| `typologie_specifique` | 145 | 10.9 % | note: the model calls this `typologie` |
| `civique_min` | 37 | 2.8 % | |
| `civique` | 99 | 7.4 % | ranges: `412-414`, `445-451` |
| `civique_max` | 37 | 2.8 % | |
| `type_de_voie` | 38 | 2.8 % | |
| `voie` | 37 | 2.8 % | |
| `est_ouest` | 822 | 61.5 % | absence is normal, not a defect |
| `arrondissement` | 0 | 0.0 % | |
| `lien` | 1130 | 84.6 % | |
| `historique_sommaire` | 1040 | 77.8 % | **the RAG text source — see §7** |
| `debut_des_travaux` | 320 | 24.0 % | |
| `fin_des_travaux` | 667 | 49.9 % | |
| `centro_x` / `centro_y` | 60 | 4.5 % | always null as a pair |

---

## 2. `arrondissement` — three separate mismatch causes

`MONTREAL_ARRONDISSEMENTS` in `utils/geo.py` matches **0 of the 1336 rows** as-is. Three
independent causes stack up:

| # | Cause | Example | Rows affected |
|---|---|---|---|
| 1 | The CSV suffixes every borough | `Ville-Marie (Montréal)` | all 1306 boroughs |
| 2 | The CSV uses an **em dash** U+2014; `geo.py` uses an **en dash** U+2013 | `Mercier—Hochelaga…` vs `Mercier–Hochelaga…` | 6 boroughs, ~183 rows |
| 3 | **Stage 02 converts `'` (U+0027) to `’` (U+2019)**; `geo.py` uses the straight form | `L’Île-Bizard…` vs `L'Île-Bizard…` | 1 borough, 18 rows |

Cause 3 is the one to remember: `_normalize_french_typography` in stage 02 is doing its job
correctly, and in doing so it invalidates a constant defined in stage 00. Normalizing the borough
name before comparison — rather than "fixing" the typography stage or hand-patching the constant —
is what keeps the two stages decoupled.

After normalizing all three (strip suffix, em→en dash, curly→straight apostrophe):

```
1306 / 1336 rows match the 19 official boroughs
  30 / 1336 rows remain
```

## 3. The remaining 30 rows are not errors

They are **villes liées** — independent municipalities of the Montreal agglomeration that are not
boroughs of the Ville de Montréal:

| Municipality | Rows |
|---|---:|
| Senneville | 10 |
| Beaconsfield | 4 |
| Dorval | 4 |
| Sainte-Anne-de-Bellevue | 3 |
| Pointe-Claire | 3 |
| Kirkland | 2 |
| Westmount | 2 |
| Baie-D'Urfé | 1 |
| Mont-Royal | 1 |
| **Total** | **30** |

These are real heritage buildings with valid coordinates and valid history. The docstring currently
on `_validate_arrondissement` — *"Reject rows whose ARRONDISSEMENT is not in the official
19-borough list"* — would delete all 30. [ADR-004](../adr/ADR-004-data-quality-policy.md) decides
against that: they are kept and tagged.

## 4. `debut_des_travaux` / `fin_des_travaux` — sentinel values, not outliers

Both columns are typed as text after stage 02 and carry **sentinel values standing in for
"unknown"**:

| | `debut_des_travaux` | `fin_des_travaux` |
|---|---:|---:|
| null | 320 | 667 |
| `0` | 7 | 242 |
| `9999` | 15 | 0 |
| valid in [1600, 2030] | 994 | 427 |
| observed valid range | 1669 – 2011 | 1670 – 2013 |
| rows where `fin < debut` | — | 0 |

`0` and `9999` are the only out-of-range values — there are no genuine outliers such as `184` or
`18466`. The `[1600, 2030]` bound is therefore doing exactly one job: catching these two sentinels.

The volume is what forces the policy: **242 rows (18 % of the dataset) carry `fin_des_travaux = 0`.**
Rejecting rows on an invalid year would cost a fifth of the corpus to encode a fact the source
already states plainly — that the end date is unknown. Nullification is the only defensible choice.

The absence of any `fin < debut` inconsistency means no cross-field arbitration is needed.

## 5. Coordinates — already WGS84, and X/Y are not in the intuitive order

| | `centro_x` | `centro_y` |
|---|---|---|
| observed range | −73.956 → −73.491 | 45.404 → 45.698 |
| corresponds to | **longitude** | **latitude** |
| nulls | 60 | 60 (same rows) |
| outside the Montreal bbox | 0 | 0 |

Two consequences:

- **The CRS question is closed.** The source is already WGS84, not Lambert NAD83 (EPSG:32198). The
  open question in `schemas.py` and the `lambert_to_wgs84()` stub in `utils/geo.py` — which raises
  `NotImplementedError("Verify the CRS of CENTRO_X/Y before implementing")` — can both be removed.
  No `pyproj` dependency is needed.
- **`centro_x` is the longitude.** `BuildingEnriched` exposes `latitude` and `longitude`, so the
  mapping is `latitude ← centro_y`, `longitude ← centro_x`. Inverting them puts every building in
  Somalia, and the bbox check in `NormalizedSchema` would not catch it — the two ranges do not
  overlap, so the error surfaces as a schema failure rather than as silently wrong coordinates.

Coordinate validation has nothing to reject: 0 rows fall outside the bounding box. The bbox
constraint is a regression guard for future data refreshes, not a filter for the current dataset.

## 6. `identifiant_batiment` — not a usable primary key

- 1335 distinct values for 1336 rows: **one duplicate**.
- **One null** — while `NormalizedSchema` declares `identifiant_batiment: Series[str]` as
  non-nullable.
- All 1336 `record_hash` values are distinct, so the two rows sharing an identifier differ in
  content; they are not a duplicated record.

`record_hash` is the only truly unique key on this dataset. `BuildingEnriched.id` maps from
`identifiant_batiment`, which means stage 04 needs a decision for the null case — covered by
[ADR-004](../adr/ADR-004-data-quality-policy.md).

## 7. `historique_sommaire` is 77.8 % null — this constrains stage 04

`BuildingEnriched.text` is the field the RAG engine retrieves on, and `historique_sommaire` is its
only natural source. **1040 of 1336 buildings have no historical summary at all**, leaving 296 with
usable narrative text.

This is out of scope for stage 03, but it needs to be settled before stage 04: running spaCy NER
over 296 documents is a very different proposition from 1336, and a `text` field built from the
summary alone would be empty for three quarters of the corpus. Composing `text` from the structured
fields (name, typology, address, borough, dates) with the summary appended when present is the
likely answer.

## 8. What the current stubs get wrong

Measured against the data, the docstrings in `s03_normalize.py` need these corrections:

| Stub | Current docstring | Reality |
|---|---|---|
| `_normalize_est_ouest` | `E → Est, O → Ouest` | The column holds only `Est` (258), `Ouest` (256), null (822). **No abbreviations exist.** The function has nothing to do on this dataset — keep it as a guard for future refreshes, or drop it. |
| `_normalize_voie_type` | `Rue → rue, Avenue → avenue` | 16 distinct values → 15 after lowercasing. The **single** case collision is `Avenue` (6) vs `avenue` (89). Also present: `road` (4), an English type that lowercasing will not translate. |
| `_validate_arrondissement` | "Reject rows" not in the 19-borough list | Would delete 30 valid buildings; and matching cannot work at all without the §2 normalization first. |
| `_cast_coordinates` | "Cast to float and validate against the bbox" | Correct, but must not implement any Lambert conversion (§5). |
| `_cast_years` | "Cast to nullable int, clamped to [1600, 2030]" | Correct in intent — but *clamping* would turn `9999` into `2030`, inventing a date. It must **nullify**, not clamp. |

## 9. Schema consequences

`NormalizedSchema` as currently written **rejects this dataset**. Three columns are declared
non-nullable but contain nulls after stage 02:

| Column | Declared | Nulls present |
|---|---|---:|
| `identifiant_batiment` | `Series[str]` | 1 |
| `nom_historique` | `Series[str]` | 30 |
| `voie` | `Series[str]` | 37 |

`arrondissement` is the only source column that is genuinely non-null (0/1336) and can stay
required. The other three must either become `nullable=True`, or stage 03 must drop those rows —
which is the decision recorded in [ADR-004](../adr/ADR-004-data-quality-policy.md).

The schema also needs a column for the borough/ville-liée distinction introduced in §3, and the
`centro_x`/`centro_y` bounds already in place (`ge=-74.1, le=-73.4` and `ge=45.3, le=45.8`) are
confirmed correct by the observed ranges.

---

## Reproducing this profile

Every figure above comes from `data/02_clean/buildings_clean.parquet`, produced by
`dvc repro` at pipeline version 0.2.0. Regenerate the input with:

```bash
make download
python -m ingestion_patrimoine_mtl --stage 01
python -m ingestion_patrimoine_mtl --stage 02
```

Re-profile after any source data refresh: the sentinel values, the dash and apostrophe variants,
and the ville-liée list are all properties of this particular extract, not guarantees from the
publisher.
