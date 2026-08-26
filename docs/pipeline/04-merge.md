# Stage 04 — `s04_merge.py`

This document explains, function by function, what `s04_merge.py` does, and states the matching
policy, the thresholds and the match rate **measured on the reference extract**.

Stage 04 is where the two ingest paths meet.

```
rawData/edifices_patrimoine.csv  → 01 → 02 → 03 ─┐
                                                  ├→ 04 merge → 05 enrich → 06 export
rawData/rpcq/*.csv               → 01b ──────────┘
```

For why the RPCQ is a secondary source at all, see
[ADR-005](../adr/ADR-005-rpcq-as-secondary-source.md). For why an uncertain pair is refused rather
than settled, see [ADR-004](../adr/ADR-004-data-quality-policy.md) — it governs this stage as
completely as it governs stage 03.

---

**Inputs**: `data/03_normalized/buildings_normalized.parquet` (1335 rows) and
`data/01b_rpcq/rpcq_raw.parquet` (179 rows, 175 distinct biens)
**Outputs**: `data/04_merged/buildings_merged.parquet` — **1335 rows, 30 columns**
and `data/04_merged/crosswalk.parquet` — **149 rows, 5 columns**

## The problem: there is no join key

The source CSV contains **zero** reference to the RPCQ. `LIEN`, which looks promising, is a street
particle — `"des"`, `"du"` — not a URL. Nothing in either file identifies the same building twice.

So the rapprochement is **fuzzy**, and it is built on the only two facts both sources state about
every record: what the building is called, and where it is.

| | Données Montréal | RPCQ |
|---|---|---|
| Name | `nom_historique` | `nom_bien` |
| Position | `centro_x` (lon) / `centro_y` (lat) | `longitude` / `latitude` |
| Naming style | "Maison Hurtubise" | "Hurtubise" |
| Coverage | 1335 buildings | 175 biens (13 % at best) |

Neither fact is sufficient alone. Montreal holds several buildings under the same historical name,
so the name cannot carry a pair; and on a Montreal terrace the neighbouring building is 3 m away,
so proximity identifies nothing either.

## Matching policy

| Rule | Value | Why |
|---|---|---|
| Candidate radius | **150 m** | Absorbs the geocoding disagreement between the two agencies without swallowing a Ville-Marie block |
| Name weight | **0.7** | The name identifies; the distance only corroborates |
| Distance weight | **0.3** | |
| Acceptance threshold | **0.70** | Where *related* biens start outscoring identical ones — see the band below |
| Ambiguity margin | **0.05** | Below this gap the top two candidates are indistinguishable, and ADR-004 forbids picking one |

`score = 0.7 × name_similarity + 0.3 × (1 − distance / 150)`

`name_similarity` is `difflib.SequenceMatcher` over the two **normalized** names — a
character-level ratio rather than a token set, because the disagreements between the sources are
mostly spelling: `St-James` against `Saint-James`, `Christ Church` against `Christchurch`.

### Why the name is normalized first

Comparing the raw labels matches almost nothing. `normalize_name` (in `utils/matching.py`) strips
accents, folds case, collapses every non-alphanumeric run to a space, and drops the **leading** run
of generic nouns:

| Corpus | RPCQ | Normalized (both) |
|---|---|---|
| `Maison Hurtubise` | `Hurtubise` | `hurtubise` |
| `Ancien hôpital général de Montréal` | `Hôpital général de Montréal` | `hopital general de montreal` |
| `L’Île-Bizard` (curly, from stage 02) | `L'Île-Bizard` | `ile bizard` |

Generic nouns go from the front **only**. `Église de l'Hôpital général` is a different bien from
`Hôpital général`, and stripping the noun wherever it appeared would collapse the two into a false
match.

The curly apostrophe is the same cross-stage coupling stage 03 already has to undo: stage 02's
`_normalize_french_typography` introduces it, correctly, and it breaks matching downstream.

## The ambiguity rule — ADR-004 applied to entity resolution

The best candidate is accepted only if the runner-up sits at least 0.05 below it. Otherwise the
building is **logged and left unmatched**.

Nine buildings come out ambiguous on the reference extract, and the two terraces among them make
the case better than any argument:

```
Ambiguous match for 9940-27-9452-01: 4 candidates within 0.05
  (92623=0.955, 92626=0.950, 92629=0.945, 92628=0.939) — left unresolved (ADR-004)
```

`Maisons Charles-Sheppard` is four adjacent, identical row houses. The RPCQ holds
`Charles-Sheppard 1` through `4`, a couple of metres apart. Every pairing scores within 0.006 of
every other. Picking the top one would fabricate a link **indistinguishable from a real one**
downstream — the same failure as clamping `9999` to `2030`.

A bien matching *several buildings* is deliberately **not** ambiguous: an RPCQ bien can be an
ensemble covering a whole terrace. 8 biens do exactly that. The resolution only has to be a
function on the building side, where each record describes one building.

## Measured results

| | Count | Share of 1335 |
|---|---:|---:|
| Matched | **149** | 11.2 % |
| Ambiguous (logged, unresolved) | **9** | 0.7 % |
| Unmatched | 1177 | 88.2 % |

The ceiling is 175, not 1335: the RPCQ open data simply does not describe the rest of the corpus
(ADR-005). Against that ceiling, 149 matched and **35 biens matched nothing** — among them
`Château De Ramezay` and `Cinéma Corona`, each one a protected Montreal building the corpus should
plausibly hold. That count is the signal worth watching on a refresh.

Protection breakdown of the 149: 106 `Classement`, 39 `Citation`, 4 `Citation / Classement`. 85 of
them are in Ville-Marie, which holds 846 of the 1335 buildings.

| Score quartile | min | Q1 | median | Q3 | max |
|---|---:|---:|---:|---:|---:|
| | 0.703 | 0.887 | 0.961 | 0.991 | 0.999 |

| Distance | min | median | Q3 | max |
|---|---:|---:|---:|---:|
| | 0.4 m | 6.6 m | 19.3 m | 136.0 m |

**102 of the 149 matched on an exact normalized name**, 47 on the fuzzy ratio. The distribution is
strongly bimodal — the median accepted pair scores 0.961 — which is why a threshold works at all:
there is very little between a confident pair and a doubtful one.

### The band around the threshold

The threshold is not a clean cut, and the honest way to document it is to show what sits either
side of it. Just below, at 0.64–0.67, the pairs are **related biens rather than the same one**:

```
0.669  saint joseph                 vs  saint joseph du sault au recollet     @ 2 m
0.643  eglise saint pierre apotre   vs  ensemble d immeubles ... saint pierre apotre  @ 42 m
0.639  college de montreal          vs  chapelle du grand seminaire de montreal       @ 48 m
```

A church against the *ensemble* it belongs to, a college against a chapel on the same grounds —
close, adjacent, and not the same building. Accepting those would be exactly the fabrication
ADR-004 forbids.

But the cut costs real pairs too, and two of them are visible right below it:

```
0.647  unity                        vs  unity building                        @ 11 m
0.624  family theatre corona        vs  cinema corona                         @ 3 m
```

Both are almost certainly the same building under two naming conventions. They are lost because
`normalize_name` has no way to know that `Family Theatre` and `Cinéma` are the same kind of thing.

And the bottom two *accepted* pairs deserve the same scepticism in the other direction:

```
0.712  couvent des soeurs grises    vs  mere des soeurs grises de montreal    @ 19 m
0.703  charles john brydges         vs  mackenzie brydges                     @ 7 m
```

Neither is obviously right. The threshold is a defensible place to draw the line, not a boundary
between true and false — which is why `score`, `method` and `distance_m` travel with every link in
the crosswalk.

### What the merge is actually for

`historique_sommaire` is the thinnest column of the corpus and the only text the NER of stage 05
reads:

| | Records with text | Share |
|---|---:|---:|
| After stage 03 | 296 | 22.2 % |
| After stage 04 | **426** | **31.9 %** |

130 buildings gained a historical text they did not have.

## Function walkthrough

### `run(cfg)` — orchestration

`_load_sources` → `_build_candidate_pairs` → `_score_candidates` → `_select_matches` →
`_build_crosswalk` → `_join_rpcq_fields` → `_fill_historique_sommaire` → `_log_match_report` →
`_validate_schema` → two Parquet writes.

### `_load_sources` → `_deduplicate_biens`

Reads both Parquet inputs and collapses the RPCQ to **one row per `bien_id`**.

Stage 01b keeps one row per export, so the 4 biens that are both classé *and* cité appear twice.
Matching against that frame would make each of them look like two near-identical candidates a hair
apart — and the ambiguity rule would then refuse them. The doubly-protected biens would be exactly
the ones the merge could never resolve.

`statut_juridique` and `regime_protection` are joined rather than picked from: `Citation /
Classement`, because both are true. Every other column takes its first non-null value.

### `_build_candidate_pairs`

Pairs each geolocated building with the biens within 150 m: **1973 pairs over 619 buildings**.

A coarse degree box runs first, so only a few thousand haversines are computed instead of
1276 × 173 = 220 000. The box is a superset of the disc, so it can only over-select.

59 buildings have no coordinates and therefore no candidate. They stay in the output with every
RPCQ column null.

### `_score_candidates`

Computes `name_similarity`, `distance_score` and the weighted `score`, plus `method`
(`exact_name` | `name_distance`). A pair with no name on either side scores 0 on the name component
and cannot clear the threshold on distance alone.

### `_select_matches` → `_log_ambiguous_pairs`

Drops everything below 0.70, then accepts the best candidate per building unless the runner-up is
within 0.05. Returns `(matches, ambiguous)`. Each ambiguous building is logged on **its own line**
with every competing bien and its score — this is a review queue, and a count gives a reviewer
nothing to review.

### `_build_crosswalk` → `_write_parquet`

`identifiant_batiment`, `bien_id`, `score`, `method`, `distance_m`, sorted by score.

The evidence travels with the link, which is what makes the threshold reviewable: raising or
lowering it without the score column is a blind change.

### `_join_rpcq_fields`

Left join, twice, both with `validate=` so a fan-out raises instead of silently inflating the
corpus. Adds `bien_id`, `match_score`, `match_method` plus `statut_juridique`,
`regime_protection`, `url_rpcq`, `url_photo`, `synthese_historique`.

Coordinates, address and construction years are **not** carried over even though the exports
publish them. The corpus states those itself, and importing a second opinion would leave two
columns disagreeing with no rule for which one wins.

### `_fill_historique_sommaire`

Fills a null `historique_sommaire` from `synthese_historique`; **never overwrites one**.

Not because the corpus text is better — the RPCQ synthèses are usually longer — but because
overwriting is an unreviewable edit. The original is gone, and a wrong match at 0.71 would
silently rewrite the history of a building nobody would think to re-check. Filling a null is
additive and reversible; replacing a value is neither.

`historique_source` records which corpus wrote the surviving text: `donnees_montreal` (296),
`rpcq` (130), null (909).

### `_log_match_report`

Matched / ambiguous / unmatched, the method breakdown, the score distribution, and RPCQ coverage
from both ends. This is the only stage whose output depends on two sources refreshed on
independent schedules — the cités export is from 2023, the classés from 2026 — so a shrinking
match rate is the first symptom of either one moving.

### `_validate_schema`

`MergedSchema` inherits `NormalizedSchema`: the merge adds columns, it does not relax the corpus.
All nine additions are nullable, and that is the contract — a non-null constraint on any RPCQ
column would assert that the rapprochement is exhaustive, which it cannot be.

## Known limitations

- **The 1177 unmatched buildings are a coverage problem, not an algorithm problem.** The open data
  exports hold 175 biens. Reaching the rest means scraping `patrimoine-culturel.gouv.qc.ca`
  (`feat/04c-rpcq-scrape`) — and the 149 pairs measured here are the validation set that says the
  matching is worth pointing at scraped pages.
- **No manual review file.** The 9 ambiguous buildings are logged, not queued into an artifact a
  human can resolve and feed back. If the scrape multiplies them, that becomes worth building.
- **The thresholds are calibrated on one extract.** They were read off the ranked pairs of the
  2026-08 data. A refresh that changes the naming conventions of either source should re-read the
  band between 0.60 and 0.75 before trusting the rate.
- **The bottom of the accepted band is not clean, and neither is the top of the rejected one.**
  Two accepted pairs at 0.70–0.71 are doubtful and at least two rejected pairs at 0.62–0.65 are
  probably real (see the band above). A name-aware synonym list — `théâtre` ≈ `cinéma`,
  `couvent` ≈ `maison mère` — would separate them better than moving the threshold, which trades
  one error for the other.
- **`SequenceMatcher` is O(n²) on name length.** Irrelevant at 1973 pairs; worth revisiting if the
  scrape pushes the candidate count by an order of magnitude.
