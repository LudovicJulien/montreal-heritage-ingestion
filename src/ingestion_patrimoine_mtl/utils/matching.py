from __future__ import annotations

import re
import unicodedata

# Words that describe what a building *is* rather than which building it is. The
# two sources disagree on them systematically — the corpus writes "Maison
# Hurtubise" where the RPCQ writes "Hurtubise", "Maisons Charles-Sheppard" where
# the RPCQ writes "Charles-Sheppard 1" — so a leading run of them carries no
# discriminating signal and only depresses the similarity of a correct pair.
#
# They are dropped only from the **front** of the name. "Ancien hôpital général"
# and "hôpital général" are the same bien; "Église de l'Hôpital général" is not,
# and stripping the noun wherever it appears would collapse the two.
GENERIC_LEADING_NOUNS: frozenset[str] = frozenset(
    {
        "ancien",
        "ancienne",
        "anciennes",
        "anciens",
        "batiment",
        "d",
        "de",
        "des",
        "du",
        "edifice",
        "edifices",
        "immeuble",
        "immeubles",
        "l",
        "la",
        "le",
        "les",
        "maison",
        "maisons",
    }
)

# Anything that is not a letter or a digit separates tokens: the two sources
# hyphenate differently ("Jacob-De Witt" against "Jacob De Witt") and the corpus
# carries the typographic apostrophe stage 02 introduces.
_NON_ALNUM = re.compile(r"[^0-9a-zA-Z]+")


def normalize_name(name: str | None) -> str | None:
    """Reduce a building name to the form the two sources can be compared on.

    Four transformations, applied in order:

    - strip the accents, so "Édifice" and "Edifice" compare equal;
    - fold the case;
    - collapse every non-alphanumeric run into a single space, which covers the
      hyphens, the straight apostrophes and the typographic ones alike;
    - drop the leading run of GENERIC_LEADING_NOUNS.

    Returns None for a null input, and also for a name made of nothing but
    generic nouns — "La Maison" normalizes to the empty string, which is not a
    name anything should be matched on.
    """
    if not isinstance(name, str):
        return None

    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    tokens = _NON_ALNUM.sub(" ", stripped).casefold().split()

    while tokens and tokens[0] in GENERIC_LEADING_NOUNS:
        tokens = tokens[1:]

    return " ".join(tokens) or None
