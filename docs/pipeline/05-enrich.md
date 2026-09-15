# Stage 05: `s05_enrich.py`

This document covers the **taxonomy half** of stage 05: `utils/taxonomy.py` and
`_normalize_typologie`, the only part of the stage implemented so far.

Stage 05 is architecturally "taxonomy + NER" on the merged corpus, but the two halves are
independent and land separately:

```
data/03_normalized ─┐
data/01b_rpcq ───────┼→ 04 merge → 05 enrich (taxonomy done, NER pending) → 06 export
                     ┘
```

`run(cfg)` still raises `NotImplementedError`. The NER half (entity extraction, JSONL assembly,
`_write_jsonl`) is a separate, not-yet-made decision (`feat/05b-ner`): `fr_core_news_lg` weighs
500 MB for a facet that can only ever read the 424 records that carry `historique_sommaire`
(31.8 % of the corpus, see [04-merge.md](04-merge.md)). Shipping the taxonomy mapping does not
wait on that decision: it reads a column NER never touches, and `feat/06-export` needs it for the
front-end's typology facet regardless of how `05b` is decided.

For why a degraded field is nulled rather than dropped or guessed, see
[ADR-004](../adr/ADR-004-data-quality-policy.md), which governs the sentinel mapping below the
same way it governs stage 03.

---

**Input measured against**: `data/04_merged/buildings_merged.parquet` (1335 rows, 2026-08-29
extract)
**Output**: none yet. `_normalize_typologie` is a private helper, tested in isolation on a
DataFrame, not wired into a DVC stage. `typologie_specifique` is 89.1 % populated (1190 of 1335);
everything below is measured on those 1190 non-null values.

## The problem: 42 raw values, most of them noise

`typologie_specifique` carries 42 distinct raw strings. Read as a facet without treatment, three
things break it:

1. **Sentinels dressed up as categories.** `"non applicable"` (309), `"indéterminée"` (157) and
   `"indéterminé"` (66) are the source's way of saying *not determined*, not a building type.
   Together they account for **532 of 1335 records, 39.9 %** of the whole corpus.
2. **Inconsistent casing.** `"Maison isolée"` (Title Case) against `"maison-magasin"` (lowercase):
   a raw `GROUP BY` on this column reports the same typology as two.
3. **Near-duplicate categories.** `"Édifice de culte"` (52) and `"Édifice religieux"` (39) describe
   the same thing, a church, a synagogue, a temple, as if they were different types.

## The mapping

`TYPOLOGIE_MAPPING` in `utils/taxonomy.py` resolves all three, keyed casefolded so a casing the
2026-08 extract never shipped still resolves on a refresh:

| Raw value(s) | Resolves to |
|---|---|
| `non applicable`, `indéterminée`, `indéterminé` | `None` (not displayed as a category) |
| `Édifice de culte`, `Édifice religieux` | `édifice religieux` |
| every other raw value | itself, casefolded |

A raw value absent from the table, one the 2026-08 extract never saw, is **not** silently nulled:
`normalize_typologie` returns it unchanged, and `_normalize_typologie` logs it once at WARNING per
distinct value, not once per row. A refresh introducing a new typology should be loud.

## Measured results

| | Records | Share of 1335 |
|---|---:|---:|
| `typologie_specifique` missing (raw) | 145 | 10.9 % |
| Resolves to a sentinel, mapped to null | 532 | 39.9 % |
| Resolves to a real category | **658** | **49.3 %** |

**38 distinct categories** survive (42 raw values, minus 3 sentinels, minus 1 for the merged
religious pair). The five largest:

| Category | Records |
|---|---:|
| `magasin-entrepôt` | 166 |
| `maison isolée` | 119 |
| `édifice religieux` | 91 |
| `maison-magasin` | 47 |
| `gratte-ciel` | 34 |

A typology facet built on this column covers under half the corpus (49.3 %) even once the mapping
is clean. The raw data, not the mapping, sets that ceiling.

## Function walkthrough

### `normalize_typologie(raw)` (`utils/taxonomy.py`)

Pure function, no I/O. `None` in, `None` out. Casefolds the input, looks it up in
`TYPOLOGIE_MAPPING`, and returns the raw value unchanged on a miss rather than raising or
nulling it silently.

### `_normalize_typologie(df)` (`pipeline/s05_enrich.py`)

Adds `typologie_normalisee` next to `typologie_specifique`, which is left untouched so a reviewer
can always trace a facet value back to what the corpus actually said. Scans the column once for
raw values `TYPOLOGIE_MAPPING` does not cover and logs each distinct one at WARNING before mapping
the column with `Series.apply`.

## Known limitations

- **Not wired into `run()`.** The function is complete and tested, but stage 05's `run()` still
  raises `NotImplementedError`: it waits on the NER decision (`feat/05b-ner`) before the stage has
  anything to write. `feat/06-export` can import `normalize_typologie` directly without waiting on
  either.
- **No DVC stage.** `s05_enrich.py` has never had a `dvc.yaml` entry, since there was nothing to
  reproduce while every function raised. Nothing in this branch changes that.
- **The mapping is read off one extract.** `TYPOLOGIE_MAPPING` reflects the 2026-08-29 snapshot of
  `typologie_specifique`. A refresh that introduces a genuinely new typology surfaces it at
  WARNING (see above) rather than silently folding it into an existing category or dropping it.
- **A 49.3 % ceiling is a floor for the front-end, not a target for this stage.** No amount of
  cleanup raises it: the other 50.7 % simply never stated a typology in the source.
