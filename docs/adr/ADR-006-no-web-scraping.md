# ADR-006: No Web Scraping — Open Data Exports Are the Only Acquisition Channel

**Status:** Accepted
**Date:** 2026-08-29
**Supersedes:** the scraping half of [ADR-005](ADR-005-rpcq-as-secondary-source.md). The open data
ingest of stage `01b` and the fuzzy rapprochement of stage `04` stand unchanged.

## Context

ADR-005 ingested the two RPCQ open data exports as stage `01b` and **deferred** scraping until the
matcher had proved itself, forward-referencing a future ADR-006 that would authorise it. This is
that ADR, and it decides the opposite.

The matcher has since been measured. Stage `04` links **147 buildings of 1335** against the 175
biens the exports describe, and fills `historique_sommaire` on 128 records that had none. So the
question ADR-005 posed — *is the rapprochement good enough to point at a larger corpus?* — is
answered yes on its own terms. The constraint that settles it is not technical.

**The project owner has determined that we are not permitted to scrape the source sites.** No
crawler, no cached HTML, no parser over pages we fetched ourselves — neither
`patrimoine-culturel.gouv.qc.ca` (the target ADR-005 deferred) nor
`montreal.ca/repertoire-patrimoine-bati` (a record-page-per-building path explored on branch
`feat/04c-mtl-scrape`, which reached working code, tests and documentation before this decision
and is abandoned unmerged). This record exists so the next contributor to notice those pages finds
the decision instead of rediscovering the design.

This ADR records a project constraint. It is not a legal analysis, and it does not characterise
the terms of either site.

## Decision

**Acquire data only from published open data exports downloaded as whole files. No stage of this
pipeline fetches a web page, and no branch reintroduces one without an ADR superseding this.**

The sources are, and remain:

| Source | Path | Licence | Acquisition |
|---|---|---|---|
| Données Montréal — édifices patrimoniaux | `rawData/edifices_patrimoine.csv` | Open data | `make download` |
| Données Québec — immeubles classés / cités | `rawData/rpcq/*.csv` | CC-BY 4.0 | `make rpcq-download` |

The pipeline shape is unchanged from ADR-005:

```
rawData/edifices_patrimoine.csv  → 01 → 02 → 03 ─┐
rawData/rpcq/*.csv               → 01b ──────────┴→ 04 merge → 05 enrich → 06 export
```

There is no stage `01c`.

## Rationale

A constraint on acquisition is not something to route around with a smaller crawl or a slower one.
Rate limiting, a polite User-Agent and an on-disk cache are engineering answers to load; they are
not answers to permission, and treating them as though they were is how a data pipeline acquires a
liability its authors did not intend.

Recording the refusal as an ADR rather than deleting the work silently is the cheaper option. The
montreal.ca path was attractive for a real reason — `identifiant_batiment` is the primary key of
that repertoire as well as of our corpus, so the join would have been exact rather than fuzzy —
and that reason will occur to the next person who reads the source CSV carefully. Without this
record they would spend the same week on it.

Dropping the channel also costs less than it looks. Every field the record pages carry is either
already in the corpus or is enrichment stage 05 derives from text we hold. What is genuinely lost
is coverage, and coverage was never within reach from scraping alone at an acceptable cost.

## Consequences

- **The enrichment ceiling is now permanent, not provisional.** 175 biens of 1336, 147 realised.
  The 1179 unmatched buildings stay unmatched, and `historique_sommaire` tops out at **424 records
  (31.8 %)**. ADR-005 framed this as a floor to be raised later; it is the ceiling.
- **Stage 05 must work on thin input.** Two records in three carry a name, an address and a pair of
  coordinates and nothing else. Enrichment that assumes a historical paragraph will produce
  nothing for most of the corpus, and should be measured on the 68 % without one, not the 32 %
  with.
- **`httpx` and `selectolax` are not dependencies.** Neither is needed by any remaining stage.
  `requests` stays for the two download scripts, which fetch published files, not pages.
- **The fuzzy crosswalk has no ground truth and will not get one.** The montreal.ca pages would
  have supplied a stated RPCQ link per building to check the inferred one against. Without it the
  147 links are validated only by `score`, `method` and `distance_m` travelling in the crosswalk,
  and by review of the band around the threshold.
- **A legitimate route to the missing fields remains open.** Our CSV is the open data export of the
  Ville de Montréal repertoire, so the richer fields exist as data on the publisher's side. A
  request through the Données Montréal portal for an extended export is compatible with this ADR;
  a crawl of the same content is not.
- **Branch `feat/04c-mtl-scrape` is deleted rather than merged**, so no crawler and no archived
  page ever enters the history of `main`. The outranked-claim rule of stage `04`, the one piece of
  that branch independent of scraping, was cherry-picked onto `feat/04c-outranked-claim`.
