"""Strand-aware genotype matching — the single source of truth for allele matching.

Pure functions, stdlib only, no I/O. Used by the diploid analyzers so strand handling
lives in exactly one place. See docs/superpowers/specs/2026-06-12-*-design.md.
"""

from dataclasses import dataclass

_BASES = {"A", "C", "G", "T"}
_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}
# Genotypes whose two alleles are each other's complement can't be strand-resolved.
_PALINDROMES = ({"A", "T"}, {"C", "G"})


def _norm(allele) -> str:
    return (allele or "").strip().upper()


def complement_base(allele) -> str | None:
    """Complement a single base (strand-aware). Returns None for non-bases."""
    return _COMPLEMENT.get(_norm(allele))


@dataclass(frozen=True)
class MatchResult:
    dosage: int | None       # copies of the effect allele: 0, 1, 2, or None
    zygosity: str | None     # homozygous_effect | heterozygous | homozygous_other | None
    status: str              # direct | strand_flipped | ambiguous_palindromic | no_match | missing
    matched: bool            # True iff a confident dosage call was made


_ZYGOSITY = {2: "homozygous_effect", 1: "heterozygous", 0: "homozygous_other"}


def _hit(dosage: int, status: str) -> MatchResult:
    return MatchResult(dosage, _ZYGOSITY[dosage], status, True)


def _miss(status: str) -> MatchResult:
    return MatchResult(None, None, status, False)


def match_snv(user_genotype, effect_allele, other_allele=None) -> MatchResult:
    """Count copies of the effect allele in a user's diploid genotype, strand-aware.

    Tries a direct match, then the reverse-complement for non-palindromic sites.
    Palindromic sites (A/T, C/G) are matched directly only and flagged if they don't fit —
    a reverse-complement there could fabricate a call.
    """
    a1, a2 = _norm(user_genotype[0]), _norm(user_genotype[1])
    eff = _norm(effect_allele)
    oth = _norm(other_allele) if other_allele is not None else ""

    if a1 not in _BASES or a2 not in _BASES:
        return _miss("missing")
    if eff not in _BASES:
        return _miss("no_match")

    def count(target: str) -> int:
        return (a1 == target) + (a2 == target)

    user = {a1, a2}
    other_known = oth in _BASES
    allowed = {eff, oth} if other_known else None

    # Direct
    if allowed is not None:
        if user <= allowed:
            return _hit(count(eff), "direct")
    elif count(eff) > 0:
        return _hit(count(eff), "direct")

    # Palindromic sites cannot be strand-resolved — never flip them.
    if other_known and {eff, oth} in _PALINDROMES:
        return _miss("ambiguous_palindromic")

    # Reverse-complement attempt (non-palindromic only).
    rc_eff = _COMPLEMENT[eff]
    rc_oth = _COMPLEMENT[oth] if other_known else ""
    if other_known:
        if user <= {rc_eff, rc_oth}:
            return _hit((a1 == rc_eff) + (a2 == rc_eff), "strand_flipped")
    else:
        rc_count = (a1 == rc_eff) + (a2 == rc_eff)
        if rc_count > 0 and count(eff) == 0:
            return _hit(rc_count, "strand_flipped")

    return _miss("no_match")


def _genotype_key_variants(a1: str, a2: str) -> list[str]:
    """All string forms a genotype_results map might use for this allele pair."""
    return [f"{a1}/{a2}", f"{a2}/{a1}", f"{a1}{a2}", f"{a2}{a1}"]


def resolve_genotype_key(user_genotype, known_keys):
    """Strand-aware resolution of a user genotype to one of a set of known genotype keys.

    Returns (matched_key, status). Tries direct orderings against known_keys, then the
    reverse-complement genotype — except palindromic genotypes, which are direct-only.
    Status is one of: direct | strand_flipped | ambiguous_palindromic | no_match | missing.
    """
    a1, a2 = _norm(user_genotype[0]), _norm(user_genotype[1])
    if a1 not in _BASES or a2 not in _BASES:
        return None, "missing"

    keyset = set(known_keys)
    for variant in _genotype_key_variants(a1, a2):
        if variant in keyset:
            return variant, "direct"

    if {a1, a2} in _PALINDROMES:
        return None, "ambiguous_palindromic"

    rc1, rc2 = _COMPLEMENT[a1], _COMPLEMENT[a2]
    for variant in _genotype_key_variants(rc1, rc2):
        if variant in keyset:
            return variant, "strand_flipped"

    return None, "no_match"


def to_reference_strand(user_genotype, allele_a, allele_b):
    """Express a user genotype on the strand where the variant's alleles are {a, b}.

    Returns an (allele1, allele2) tuple on the reference strand, or None if the genotype is
    a no-call or the site is palindromic (can't be strand-resolved). Used for haplotype
    calling (e.g. APOE) where the actual allele identities matter, not just a dosage.
    """
    a1, a2 = _norm(user_genotype[0]), _norm(user_genotype[1])
    if a1 not in _BASES or a2 not in _BASES:
        return None
    a, b = _norm(allele_a), _norm(allele_b)
    ref = {a, b}
    # Palindromic sites cannot be strand-resolved — refuse even a direct-looking hit.
    if ref in _PALINDROMES:
        return None
    if {a1, a2} <= ref:
        return (a1, a2)
    if {a1, a2} <= {_COMPLEMENT[a], _COMPLEMENT[b]}:
        return (_COMPLEMENT[a1], _COMPLEMENT[a2])
    return None


def match_indel(user_genotype, risk_allele, normal_allele=None) -> MatchResult:  # normal_allele reserved; not yet used
    """Match curated indel risk alleles against AncestryDNA I/D markers.

    Risk alleles are insertion (insC, insT, ...) or deletion (delAG, delCTT, ...) forms,
    or a literal I/D. The curated `normal_allele` for these entries is '-' (the reference,
    no-indel state) — it is not itself a risk allele, so a bare '-' risk allele is treated
    as unrecognized (no_match). Conservative: flags rather than guesses.

    NOTE: the parser currently filters I/D genotypes as no-calls, so in the live pipeline
    this returns 'missing' until that filter is lifted (tracked for a later tier). Tested
    here in isolation so the behaviour is correct when indel genotypes are available.
    """
    risk = _norm(risk_allele)
    if risk.startswith("INS"):
        marker = "I"
    elif risk.startswith("DEL"):
        marker = "D"
    elif risk in ("I", "D"):
        marker = risk
    else:
        return _miss("no_match")

    a1, a2 = _norm(user_genotype[0]), _norm(user_genotype[1])
    if a1 not in ("I", "D") or a2 not in ("I", "D"):
        return _miss("missing")
    return _hit((a1 == marker) + (a2 == marker), "direct")
