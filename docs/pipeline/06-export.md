# Stage 06: `s06_export.py`

This document explains, function by function, what `s06_export.py` does, and states the artifact
contract the front-end reads, with counts measured on the reference extract.

Stage 06 is the last stage this pipeline runs today.

```
rawData/edifices_patrimoine.csv  → 01 → 02 → 03 ─┐
                                                  ├→ 04 merge → 05 enrich → 06 export
rawData/rpcq/*.csv               → 01b ──────────┘
```

`05 enrich` sits in the graph but not in the data path stage 06 reads: its `run()` still
`raise NotImplementedError`s (only the taxonomy mapping of `feat/05a-taxonomy` is implemented,
as a public function in `utils/taxonomy.py`), so stage 06 reads stage 04's output directly and
calls that mapping itself. See *Why no dependency on stage 05* below.

---

**Input**: `data/04_merged/buildings_merged.parquet` (1335 rows)
**Outputs**: `data/06_export/buildings.geojson` (1276 features), `data/06_export/buildings.json`
(1335 records), `data/06_export/stats.json` (one document)

## Why static files, no API

The front-end reads three files over HTTP, the same way it would read any other static asset.
ADR-002 chose DVC over an orchestrator for the pipeline itself on reproducibility grounds; the same
reasoning extends to what the pipeline hands the front-end. A precomputed, DVC-tracked JSON file is
deterministic and versioned; a server that recomputes facets on every request is neither, and this
project has no server to run one on. `buildings.geojson` feeds a map layer, `buildings.json` feeds
the list and detail views (including the 59 buildings the map cannot place), and `stats.json` feeds
the dashboard so the front-end never recomputes a facet count client-side.

## Why no dependency on stage 05

`typologie` is the one field stage 05 was going to carry into the enriched record. Stage 05's
`run()` is still a NER pipeline with nothing to run: `_extract_entities`, `_build_enriched_record`
and `_write_jsonl` all `raise NotImplementedError`. The taxonomy mapping `feat/05a-taxonomy` landed
is a public, already-tested function (`normalize_typologie`, `utils/taxonomy.py`), not something
only stage 05's incomplete `run()` produces. Stage 06 imports it directly instead of waiting on the
NER decision `feat/05b-ner` still has to make.

## Function walkthrough

### `run(cfg)`: orchestration

`_load_source` → `_map_coordinates` → `_compose_adresse` → `_add_montreal_url` →
`_build_public_frame` → `_build_geojson` / `_records` / `_build_stats` → three JSON writes →
`_log_export_report`.

### `_map_coordinates`

Renames `centro_x`/`centro_y` to `longitude`/`latitude`. `CENTRO_X` is the **longitude**, the same
invariant stage 03's bbox check guards, restated here because a front-end map has no schema to
catch the swap: it would just place every building in Somalia, silently.

### `_compose_adresse`

Builds `adresse` from `civique_min`/`civique_max`, not from the source's own pre-formatted
`civique` column. On the merged extract, `civique` is null on 99 records against 37 for
`civique_min`/`civique_max`: trusting `civique` alone would drop the address entirely on 62
records. It also sometimes disagrees with its own bounds outright (a `civique` of `"305-307"`
against a `civique_min` of `301` and `civique_max` of `305`). Reconstructing the range from the
parsed bounds is the reliable path.

37 records have no `voie` at all; `adresse` is null for exactly those, not a partial string built
from whatever field happens to be present.

### `_add_montreal_url`

Builds `https://montreal.ca/repertoire-patrimoine-bati/batiments-patrimoniaux/{identifiant_batiment}`
for every record. A link, never a fetch (ADR-006): the URL is a string built from a column already
in hand, no request is made, and `identifiant_batiment` is guaranteed non-null since stage 03
already rejects the one row of the corpus that lacks one.

### `_build_public_frame`

Reduces the merged corpus to `BuildingPublic`'s column set. Adds `typologie` through
`normalize_typologie`; carries `url_rpcq`, `url_photo`, `statut_juridique` and
`historique_sommaire` straight through, already null for the 1188 buildings the RPCQ exports do
not cover (ADR-005).

### `_records`

Converts a frame to plain dicts with JSON-safe nulls. pandas' own missing markers (`NaN`, `pd.NA`,
`NaT`) are not valid JSON; `.where(df.notna(), None)` replaces every one with `None` before the
frame reaches `json.dumps`, rather than leaning on a custom encoder.

### `_build_geojson`

FeatureCollection over the records with coordinates only: **1276 of 1335**. The 59 without a
`centro_x`/`centro_y` pair are excluded here, not passed through with a null geometry: a
null-geometry Feature is valid GeoJSON but useless to a map layer. They stay in `buildings.json`,
which the list and detail views read without needing a position.

### `_build_stats`

Precomputes `total_buildings`, `buildings_with_coordinates`, and three facets:
`by_arrondissement`, `by_decade` (via `_decade_histogram`), `by_typologie` and
`by_statut_juridique` (via `_value_counts`). Only non-null values enter a facet count. A "no data"
bucket dressed up as a filterable category is the same fabrication ADR-004 rules out for a single
field, applied here to a facet instead.

`_decade_histogram` buckets `debut_travaux` only, not `fin_travaux`: the latter is null more than
twice as often (32.0% known against 74.5%), and a construction timeline needs one endpoint per
building, not two disagreeing ones.

### `_log_export_report`

Logs the building count, the mapped-feature count, the count without coordinates, and the byte
size of each of the three artifacts written.

## Measured results

Measured on `data/04_merged/buildings_merged.parquet`, 1335 rows.

| | Count | Share of 1335 |
|---|---:|---:|
| `buildings.geojson` features | **1276** | 95.6 % |
| `buildings.json` records | **1335** | 100 % |
| Without coordinates (map-excluded) | 59 | 4.4 % |

| Facet | Populated | Share |
|---|---:|---:|
| `arrondissement` | 1335 | 100 % (27 distinct values) |
| `nom_historique` | 1305 | 97.8 % |
| `adresse` | 1298 | 97.2 % |
| `typologie` (post-taxonomy) | 658 | 49.3 % |
| `debut_travaux` | 994 | 74.5 % (1669 to 2011) |
| `fin_travaux` | 427 | 32.0 % |
| `historique_sommaire` | 424 | 31.8 % |
| `statut_juridique` | 147 | 11.0 % (104 Classement, 39 Citation, 4 Citation / Classement) |
| `url_photo` | 136 | 10.2 % |

`typologie`'s 49.3% is lower than `typologie_specifique`'s own 89.1% fill rate: the taxonomy
mapping folds `"non applicable"`, `"indéterminée"` and `"indéterminé"` onto null rather than
displaying them as a category (`feat/05a-taxonomy`, ADR-004). Those three sentinels alone cover
532 records, 39.9% of the 1335.

Ville-Marie alone accounts for 846 of the 1335 buildings (63.4%) and 83 of the 147
RPCQ-protected ones.

## Known limitations

- **No dependency on stage 05's `run()` is a deliberate decoupling, not a placeholder for one.**
  If `feat/05b-ner` ever lands a named-entities facet, it becomes a fourth stage-06 input read
  from wherever that stage ends up writing it, not a resurrection of a stage-05 dependency.
- **`stats.json` recomputes over the full frame on every run.** At 1335 rows this costs nothing;
  it would need reconsidering only at a scale this corpus is not going to reach.
- **The montreal.ca URL is unverified.** It is built from `identifiant_batiment` by the same
  pattern ADR-006 records having explored on `feat/04c-mtl-scrape`, but nothing in this pipeline
  ever requests it. A renumbering on the Ville's side would break every link silently.
