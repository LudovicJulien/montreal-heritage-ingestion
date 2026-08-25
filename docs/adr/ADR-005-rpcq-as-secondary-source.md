# ADR-005: RPCQ as a Secondary Source — Open Data Export Before Scraping

**Status:** Accepted
**Date:** 2026-08-24

## Context

The Données Montréal extract is thin where it matters most for a reader. Measured on the 1335 rows
stage 03 writes, `historique_sommaire` is populated on **296 records (22.2 %)**: four buildings in
five carry a name, an address and a pair of coordinates, and nothing that says what they are.

The Répertoire du patrimoine culturel du Québec (RPCQ) documents roughly 3400 biens for the
Montreal region, each with a `description_bien`, a `synthese_historique`, a photograph and a
canonical URL. It is the obvious complement. It is available in two forms:

| Form | Coverage | Cost |
|---|---|---|
| **Open data exports** (Données Québec, CC-BY 4.0) | Only the *legally protected* biens | One HTTP download, no parsing risk |
| **The RPCQ website** | Everything | Scraping, a fetch cache, terms-of-use review |

The exports are far smaller than the site suggests. Counted on the real files:

- **immeubles classés** (updated 2026-05-11): 621 records, of which **131** in the Montreal
  administrative region.
- **immeubles cités** (updated 2023-06-26): 730 records, of which **48** in Montreal.

That is **179 rows for 175 distinct biens** — 4 are both classé and cité — against a corpus of
1336. The exports can cover at most 13 % of the buildings.

There is also no join key. `LIEN` in the Données Montréal CSV is a street particle (`"des"`,
`"du"`), not a URL, and the source file contains **zero** occurrences of `patrimoine-culturel`.
Any rapprochement between the two sources has to be inferred from names and positions.

## Decision

**Ingest the two open data exports first, as stage `01b`, and defer scraping until the matching
algorithm has been validated against them.**

Stage `01b` is a parallel ingest path: it reads `rawData/rpcq/*.csv`, reconciles the two column
layouts, keeps the Montreal administrative region, and writes `data/01b_rpcq/rpcq_raw.parquet`.
It never touches the Données Montréal corpus. The two sources meet at stage `04`, which resolves
them against each other.

The 179 known-protected biens are the **validation set** for that resolution. Scraping
(`feat/04c`, ADR-006) only starts once the matcher's behaviour on them is measured.

## Rationale

Entity resolution without a join key is the risky part of this work, not the data acquisition. The
exports hand us 179 records whose identity is independently verifiable — a bien classé carries its
address, its municipality and its coordinates from the ministry itself — which is exactly what is
needed to tell a working matcher from one that looks like it works. Scraping 3400 pages before
knowing whether names and coordinates can be matched at all would spend the expensive effort on
the unproven assumption.

The open data path also costs nothing in reproducibility. Two CC-BY 4.0 CSVs downloaded by
`make rpcq-download` behave exactly like the Données Montréal source already does under ADR-002:
a file on disk, declared as a DVC dependency, identical on every run. A scraper is not, which is
what forces the separate fetch-cache design of ADR-006.

Filtering on `region_admin` rather than on `municipalite` is deliberate. The Montreal
administrative region is the whole agglomeration; filtering on the city name would drop
Baie-D'Urfé, Beaconsfield, Kirkland, Westmount and the other villes liées, whose buildings the
Données Montréal corpus does contain — stage 03 already tags 30 of them as `ville_liee`.

## Consequences

- The enrichment ceiling from open data alone is **13 % of the corpus** (175 biens of 1336), and
  the join is fuzzy on top of that, so the realised rate will be lower. This ADR does not solve
  the 77.8 % of buildings with no historical text; it makes the attempt measurable.
- The two exports disagree on almost everything mechanical — separator, BOM, and the names of
  seven columns (`de`/`debut_construction`, `autorite`/`autorite_protection`,
  `usage`/`usage_princ`, …). Reconciliation is a permanent maintenance surface: a refresh that
  renames a column breaks stage `01b` loudly, which is the intended failure mode.
- Coordinates arrive in two shapes: the cités export publishes `latitude`/`longitude`, the classés
  export only a WKT `MULTIPOINT`. Stage `01b` casts both to float, the single exception to its
  otherwise `dtype=str` rule, so the schema can bound-check the position.
- `bien_id` is **not unique** in the output: a doubly-protected bien appears once per regime,
  distinguished by `regime_protection`. Stage 04 must key its crosswalk accordingly.
- Stage `01b` has **no idempotence filter**, unlike stage 01. It rewrites the full Montreal subset
  on every run because stage 04 needs the complete reference set to match against; a filtered
  second run would hand it an empty frame.
- The vintages differ by three years (2026-05-11 against 2023-06-26). A cited building demolished
  or de-cited since 2023 is still in our corpus.
