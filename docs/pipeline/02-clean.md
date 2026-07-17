# Stage 02 — `s02_clean.py`

This document explains, function by function, what `s02_clean.py` does, with examples taken from the project's real data (`data/01_raw/buildings_raw.parquet` and `data/02_clean/buildings_clean.parquet`).

For architectural context (why four stages, why Parquet, why a SHA-256 hash), see [ADR-001](../adr/ADR-001-four-stage-pipeline-architecture.md) and [ADR-003](../adr/ADR-003-sha256-row-hashing-for-idempotence.md).

Previous stage: [01 — Ingest](01-ingest.md).

---

**Input**: `data/01_raw/buildings_raw.parquet`
**Output**: `data/02_clean/buildings_clean.parquet`

This stage performs **no imputation** of missing values — only text normalization, in a specific order (each sub-step depends on the result of the previous one).

### 1. `_strip_html` (columns `HTML_COLS` = `nom_historique` and `historique_sommaire`)

Removes HTML tags and decodes entities, via BeautifulSoup. `<sup>`/`<sub>` tags are inlined first by regex, to avoid inserting a spurious space inside the word.

**Real example** — building `0039-39-2034-00`, column `historique_sommaire`:

| | Value |
|---|---|
| **RAW** | `...un grossiste de « marchandises sèches&nbsp;&raquo; (<i>dry goods</i>), puis...` |
| **CLEAN** | `...un grossiste de « marchandises sèches » ( dry goods ), puis...` |

The `<i>` tag disappears and the HTML entities (`&nbsp;`, `&raquo;`) are decoded to plain text by `get_text()`.

**Real example** — column `nom_historique` (5 records affected in the current dataset):

| | Value |
|---|---|
| **RAW** | `<i>St Michael's Aimish Lutherian Church Home</i>` |
| **CLEAN** | `St Michael's Aimish Lutherian Church Home` |

> `nom_historique` contained tags (`<i>`, `<sup>`) and an undecoded numeric HTML entity until `_strip_html` was applied to it as well — initially, only `historique_sommaire` went through this function. `HTML_COLS` now lists both affected columns explicitly, so that a future free-text column is not overlooked the same way.

### 2. `_fix_encoding` (all text columns, via `ftfy`)

Fixes residual encoding artifacts — mojibake, badly decoded entities, and so on.

**Real example** — building `9999-19-0004-01`, column `nom_historique`:

| | Value |
|---|---|
| **RAW** | `Entrepôt de la brasserie Dawes &#38; Co.` |
| **CLEAN** | `Entrepôt de la brasserie Dawes & Co.` |

`&#38;` is a numeric HTML entity (the code for `&`) which, before `_strip_html` was extended to `nom_historique` (see section 1), was only fixed by `ftfy` — it is now decoded upstream by BeautifulSoup as well; `ftfy` remains responsible for pure mojibake (e.g. `Ã©` → `é`).

> Note: in this dataset, most accented characters (`é`, `ç`, `â`, etc.) that *look* corrupted are in fact valid Unicode code points — a terminal display issue, not mojibake. `ftfy` therefore leaves them untouched, which is the expected behavior (there is nothing to fix).

### 3. `_collapse_whitespace` (all text columns)

Collapses repeated spaces and line breaks into a single space, then trims.

**Real example** — building `0039-39-7693-00`, column `historique_sommaire`:

| | Value |
|---|---|
| **RAW** | `...Stone supervise l'ensemble des travaux. \n\nEn janvier 1901, les bâtiments abritan...` |
| **CLEAN** | `...Stone supervise l'ensemble des travaux. En janvier 1901, les bâtiments abritant...` |

The double line break becomes a single space.

### 4. `_normalize_french_typography` (all text columns)

Two transformations:
- Straight apostrophe `'` (U+0027) → typographic apostrophe `’` (U+2019).
- Text between ASCII quotes `"..."` → French guillemets `« ... »` with non-breaking spaces.

**Real example** (apostrophe) — building `0040-00-5947-04`:

| | Value |
|---|---|
| **RAW** | `...le commerce d'articles de musique...` |
| **CLEAN** | `...le commerce d’articles de musique...` |

**Illustrative example** (guillemets — the current dataset contains no straight ASCII quotes, so this example is synthetic):

| | Value |
|---|---|
| **Before** | `Il nomme le bâtiment "Maison du Try"` |
| **After** | `Il nomme le bâtiment « Maison du Try »` |

### 5. `_empty_to_none` (all text columns)

Converts empty strings `''` to a null value — including those that became empty *after* whitespace collapsing (e.g. a cell that only contained a line break).

**Real example** — building `0040-66-4289-00`, column `historique_sommaire`:

| | Value |
|---|---|
| **RAW** | `"\n"` (a single empty line) |
| **After `_collapse_whitespace`** | `""` |
| **CLEAN (`_empty_to_none`)** | null value (`pd.NA` or `NaN`, depending on the column dtype) |

The total number of cells nullified at this step is logged (`Converted {n} empty strings to null`).

### `_text_columns` — text column selection (pandas 3.0 compatibility)

Utility function shared by `_fix_encoding`, `_collapse_whitespace`, `_normalize_french_typography` and `_empty_to_none` to identify the text columns to process.

It replaces `df.select_dtypes(include="object")`: as of pandas 3.0, text columns may be stored under the new `string` dtype rather than `object`, and `select_dtypes(include=["object", "str"])` raises a `TypeError`. `_text_columns` therefore checks each column individually via `pd.api.types.is_object_dtype` and `is_string_dtype`, which works for both dtypes.

As a consequence, the null sentinel produced by `_empty_to_none` is no longer guaranteed to be `pd.NA` by identity (`is pd.NA`) — it depends on the column dtype. Any null check must use `pd.isna(...)`.

### `_validate_schema`

Validates against `CleanSchema` (same nullability constraints as `RawSchema` for the source columns; the stage 01 pipeline metadata columns are not part of the output schema).

### `_write_parquet`

Writes snappy Parquet to `data/02_clean/buildings_clean.parquet`.
