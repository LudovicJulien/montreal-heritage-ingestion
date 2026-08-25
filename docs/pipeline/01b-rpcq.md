# Stage 01b — `s01b_rpcq.py`

This document explains, function by function, what `s01b_rpcq.py` does, and profiles what the RPCQ
open data actually contains — including what it does **not** cover.

Stage 01b is a **parallel ingest path**, not a step inserted into the chain. It never reads the
Données Montréal corpus. The two sources meet at [stage 04 — Merge](04-merge.md).

```
rawData/edifices_patrimoine.csv  → 01 → 02 → 03 ─┐
                                                  ├→ 04 merge → 05 enrich → 06 export
rawData/rpcq/*.csv               → 01b ──────────┘
```

For why the open data exports come before scraping, see
[ADR-005](../adr/ADR-005-rpcq-as-secondary-source.md).

---

**Input**: `rawData/rpcq/immeubles_classes.csv` and `rawData/rpcq/immeubles_cites.csv`
(downloaded from Données Québec via `make rpcq-download`)
**Output**: `data/01b_rpcq/rpcq_raw.parquet` — **179 rows, 25 columns**

## What the open data covers

The RPCQ website documents roughly 3400 biens for the Montreal region. The open data exports
publish only the **legally protected** ones:

| Export | Records | Montreal region | Updated | Licence |
|---|---:|---:|---|---|
| Immeubles patrimoniaux **classés** (by the minister) | 621 | **131** | 2026-05-11 | CC-BY 4.0 |
| Immeubles patrimoniaux **cités** (by municipalities) | 730 | **48** | 2023-06-26 | CC-BY 4.0 |
| **Merged, Montreal region** | 1351 | **179** | | |

179 rows for **175 distinct biens**: four are both classé *and* cité, so they appear once per
export. Against a corpus of 1336 buildings, the exports can reach at most **13 %**. Everything
else exists only on `patrimoine-culturel.gouv.qc.ca`.

The two exports also disagree on almost everything mechanical:

| | classés | cités |
|---|---|---|
| Separator | `;` | `,` |
| Encoding | UTF-8 **with BOM** | UTF-8 |
| Coordinates | `Wkt_Multipoint_XY` only | `latitude` / `longitude` |
| Construction years | `debut_construction` / `fin_construction` | `de` / `a` |
| Protecting authority | `autorite_protection` | `autorite` |
| Legal status | `statut_juridique_princ` | `statut_juridique` |
| Main use | `usage_princ` | `usage` |
| Region number | `no_regn_admin` | `no_region_admin` |
| Columns | 31 | 26 |

### `run(cfg)` — orchestration

Loads both exports into one reconciled frame, filters to the Montreal region, hashes, stamps the
run metadata, validates against `RpcqRawSchema`, and writes Parquet. Every step logs its counts.

### `_ensure_sources_exist`

Checks that **both** exports are on disk before anything else, and names `make rpcq-download` in
the error. Same fail-fast contract as stage 01.

### `_load_exports` → `_prepare_export`

Reads each export with its own dialect, brings it onto the reconciled layout, and concatenates:
621 + 730 = **1351 rows**. Alignment happens *before* the concatenation, so the merged frame is
rectangular rather than the ragged union of two different header rows.

`_prepare_export` chains, per export: `_read_csv` → `_normalize_column_names` →
`_tag_protection_regime` → `_extract_coordinates` → `_reconcile_columns`.

### `_read_csv`

Reads with `dtype=str`, the same raw-fidelity rule as stage 01. This is not cosmetic here: the
cités export writes approximate years as free text, and casting at read time would silently
nullify them.

```
de = "vers 1732" · "après 1806" · "vers 1845" · "après 1769"
```

8 of the 179 Montreal records carry a year in that form.

### `_normalize_column_names`

Strips and lowercases. The classés export mixes cases inside a single header row —
`Wkt_Multipoint_XY` sits next to `nom_bien` — so this is not a no-op.

The BOM is handled at read time by `encoding="utf-8-sig"`; without it the first column would be
named `﻿nom_bien` and every lookup of `nom_bien` would fail.

### `_tag_protection_regime`

Adds `regime_protection`, `classe` or `cite`, from the file the row came from. The regime is
carried by the export, not by a column.

This is what keeps the four doubly-protected biens legible: they share a `bien_id` across the two
files, and without the tag the concatenation would look like it had produced duplicates.

```
bien_id 93001 → (classe, "Classement", Ministre de la Culture…)
bien_id 93001 → (cite,   "Citation",   Municipalité)
```

### `_extract_coordinates`

The one place the two layouts differ by more than a name. The cités export publishes
`latitude`/`longitude`; the classés export publishes only a WKT geometry:

```
MULTIPOINT ((-73.567699 45.514985))   →   longitude = -73.567699, latitude = 45.514985
```

**The axis order is X then Y — the first number is the longitude.** Reading it the other way
round puts every building in Somalia, and the bbox check catches it only as a schema failure,
never as silently wrong data. This mirrors the `centro_x` / `centro_y` convention of stage 03.

Four of the 621 classés carry several points; the first is kept — it is the position the RPCQ
itself displays. A published coordinate always wins over the geometry; the WKT only fills gaps.

Both columns come out as `float64`, the single exception to this stage's `dtype=str` rule, and the
only reason `RpcqRawSchema` can bound-check the position at all.

**2 of the 179 Montreal records carry no position.** They are kept with null coordinates (ADR-004:
a missing field degrades the field, not the record).

### `_reconcile_columns`

Renames each export onto the canonical set, then `reindex`es onto `RPCQ_COLUMNS`, which both
drops the export-specific columns and materialises the ones an export simply does not have.

Dropped from the classés export: `terrain_protege_situation`, `Wkt_Pg_terrain_protege`,
`aire_de_protection_situation`, `Wkt_pg_aire_de_protection`, `date_attri_aire_protection`,
`version`, and the photo credit columns. Dropped from the cités export: `geometrie` (empty in the
published file), `type_periode_premiere_construction`, and the same photo credits.

### `_filter_montreal_region`

Keeps `region_admin == "Montréal"`: 1351 → **179**.

The filter is on the **region**, not the municipality. The Montreal administrative region is the
whole agglomeration, so filtering on the city name would drop the villes liées — whose buildings
the Données Montréal corpus does contain, and which stage 03 already tags as `ville_liee`:

| municipalite | records |
|---|---:|
| Montréal | 166 |
| Kirkland | 4 |
| Westmount | 2 |
| Beaconsfield | 2 |
| Pointe-Claire | 2 |
| Sainte-Anne-de-Bellevue | 1 |
| Baie-D'Urfé | 1 |
| `Westmount¤Montréal` | 1 |

That last one is not a typo — see *Multi-value fields* below.

### `_add_row_hashes`

Reuses `compute_row_hash` (ADR-003) on the reconciled source columns, before the run metadata is
appended. `regime_protection` is inside the hash: it is a fact about the record, not about the
run, and it is what gives the two rows of a doubly-protected bien distinct hashes.

### `_add_metadata`

Appends `ingested_at` (UTC), `source_file` and `pipeline_version`. Unlike stage 01 there are two
source files, so `source_file` is resolved per row from `regime_protection` rather than read off a
single setting.

### `_log_source_report`

Logs the regime split, the distinct-bien count, and fill rates. The RPCQ is refreshed
independently of the Données Montréal corpus and the two exports are three years apart in vintage;
these counts are what makes a shrinking export or a newly empty column visible on the next run
instead of at stage 04.

Measured on the current extract:

| Column | Fill rate |
|---|---|
| `url_rpcq` | 179/179 (100 %) |
| `municipalite`, `adresse`, `sous_usage` | 179/179 (100 %) |
| `description_bien` | 178/179 (99.4 %) |
| `synthese_historique` | 178/179 (99.4 %) |
| `debut_construction` | 177/179 (98.9 %) |
| `latitude` / `longitude` | 177/179 (98.9 %) |
| `fin_construction` | 171/179 (95.5 %) |
| `url_photo` | 165/179 (92.2 %) |

Compare with the 22.2 % fill rate of `historique_sommaire` in the Données Montréal corpus: where
the RPCQ covers a building, it covers it well. It just covers few of them.

### `_validate_schema` / `_write_parquet`

Validates against `RpcqRawSchema` before writing — `bien_id` non-null, `regime_protection` in
`{classe, cite}`, coordinates inside the Montreal box or null.

`bien_id` is **not** declared unique, by design: four biens legitimately appear twice.

`statut_juridique` carries **no allowlist**. The classés export already holds one
`"Avis d'intention de classement prorogé"` alongside 620 `"Classement"`, and a refresh may add
more statuses; pinning the list would turn a normal ministerial act into a pipeline failure.

The whole Montreal subset is rewritten on every run, with **no idempotence filter**. Stage 01's
filter returns only rows a previous run has not seen, which is the right contract for an
append-oriented corpus; here stage 04 needs the complete RPCQ reference set to match against, and
a filtered second run would hand it an empty frame.

## Multi-value fields

The RPCQ packs repeated values into one cell with a `¤` (U+00A4) separator, on the 179 Montreal
records:

| Column | Rows with `¤` |
|---|---:|
| `adresse` | 79 |
| `usage_princ` | 27 |
| `sous_usage` | 27 |
| `municipalite` | 1 |

```
adresse = "230 rue Sherbrooke Est¤250 rue Sherbrooke Est¤260 rue Sherbrooke Est"
```

Stage 01b **preserves them verbatim** — ingestion does not interpret. Splitting is stage 04's
problem, and it matters there: a bien spanning four civic numbers has four chances to match a
Données Montréal address, and the one bien whose `municipalite` reads `Westmount¤Montréal`
straddles a municipal boundary.

## What this stage does not give you

- **No join key to the Données Montréal corpus.** `LIEN` in the source CSV is a street particle
  (`"des"`, `"du"`), not a URL, and the file contains zero occurrences of `patrimoine-culturel`.
  The rapprochement at stage 04 is necessarily fuzzy.
- **No coverage of the unprotected majority.** 175 biens against 1336 buildings. The 179 rows are
  a validation set for the matcher before scraping, not the enrichment itself.
- **No typing.** Years stay text (`"vers 1732"`), dates stay text. Only the coordinates are cast.

Next stage: [04 — Merge](04-merge.md).
