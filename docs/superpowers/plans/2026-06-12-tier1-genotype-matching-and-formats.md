# Tier 1: Strand-aware Genotype Matching, Formats, Tests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dna-analyzer's variant matching strand-correct, add 23andMe + zip support, and stand up a pytest suite — fixing the silent false-negative where a reverse-complement carrier of a pathogenic variant is dropped.

**Architecture:** A new pure-function module `analyzers/genotype_match.py` becomes the single source of truth for allele matching. `health_risks.py` and `traits.py` are refactored to call it; `pharmacogenomics.py` gets an honesty stopgap (its data is structurally disconnected — full fix is Tier 1.5). The parser gains adaptive column detection for 23andMe's 4-column layout and in-memory zip unwrapping. Everything is TDD with tiny synthetic fixtures — no real genetic data enters the repo.

**Tech Stack:** Python 3, stdlib (`dataclasses`, `zipfile`, `io`, `re`), pytest (dev dependency), existing Flask app.

**Spec:** `docs/superpowers/specs/2026-06-12-tier1-genotype-matching-and-formats-design.md`

---

## File Structure

- Create: `analyzers/genotype_match.py` — `MatchResult`, `reverse_complement`, `match_snv`, `resolve_genotype_key`, `to_reference_strand`, `match_indel`. Pure, stdlib-only, no I/O.
- Create: `tests/__init__.py`, `tests/conftest.py` — fixture helpers.
- Create: `tests/test_genotype_match.py` — exhaustive matcher unit tests.
- Create: `tests/test_parser.py` — AncestryDNA + 23andMe (txt/zip) + malformed.
- Create: `tests/test_analyzers_integration.py` — the strand regression test.
- Create: `tests/fixtures/` — tiny synthetic raw files.
- Create: `requirements-dev.txt` — `pytest`.
- Modify: `analyzers/health_risks.py` — curated loop, ClinVar loop, APOE reads → matcher.
- Modify: `analyzers/traits.py` — `_lookup_phenotype` → strand-aware `resolve_genotype_key`.
- Modify: `analyzers/pharmacogenomics.py` — honesty stopgap (no fabricated NM; keep DB drugs).
- Modify: `analyzers/parser.py` — adaptive default columns (23andMe), zip helper.
- Modify: `app.py` — route uploaded bytes through the zip-aware text reader.

---

## Task 1: Matcher scaffolding + `reverse_complement`

**Files:**
- Create: `analyzers/genotype_match.py`
- Create: `tests/__init__.py`, `tests/test_genotype_match.py`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Create the dev dependency file and tests package**

Create `requirements-dev.txt`:
```
pytest>=8.0
```
Create empty `tests/__init__.py` (no content).

Install: `pip install -r requirements-dev.txt`

- [ ] **Step 2: Write the failing test**

Create `tests/test_genotype_match.py`:
```python
from analyzers.genotype_match import reverse_complement


def test_reverse_complement_basic():
    assert reverse_complement("A") == "T"
    assert reverse_complement("T") == "A"
    assert reverse_complement("C") == "G"
    assert reverse_complement("G") == "C"


def test_reverse_complement_lowercase_and_whitespace():
    assert reverse_complement(" a ") == "T"


def test_reverse_complement_non_base_returns_none():
    assert reverse_complement("I") is None
    assert reverse_complement("") is None
    assert reverse_complement(None) is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_genotype_match.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError: cannot import name 'reverse_complement'`.

- [ ] **Step 4: Write minimal implementation**

Create `analyzers/genotype_match.py`:
```python
"""Strand-aware genotype matching — the single source of truth for allele matching.

Pure functions, stdlib only, no I/O. Used by the diploid analyzers so strand handling
lives in exactly one place. See docs/superpowers/specs/2026-06-12-*-design.md.
"""

from dataclasses import dataclass

_BASES = {"A", "C", "G", "T"}
_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}
# Genotypes whose two alleles are each other's complement can't be strand-resolved.
_PALINDROMES = ({"A", "T"}, {"C", "G"})
# Anything not a real base is a no-call for the SNV path (indels handled separately).
_SNV_NO_CALLS = {"", "-", "--", "0", "00", ".", "N", "NN", "I", "D"}


def _norm(allele) -> str:
    return (allele or "").strip().upper()


def reverse_complement(allele) -> str | None:
    """Complement a single base (strand-aware). Returns None for non-bases."""
    return _COMPLEMENT.get(_norm(allele))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_genotype_match.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add requirements-dev.txt tests/__init__.py tests/test_genotype_match.py analyzers/genotype_match.py
git commit -m "Add genotype_match scaffolding + reverse_complement"
```

---

## Task 2: `match_snv` — direct matching + zygosity

**Files:**
- Modify: `analyzers/genotype_match.py`
- Test: `tests/test_genotype_match.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_genotype_match.py`:
```python
from analyzers.genotype_match import match_snv, MatchResult


def test_match_snv_direct_homozygous_effect():
    r = match_snv(("A", "A"), effect_allele="A", other_allele="G")
    assert r.dosage == 2
    assert r.zygosity == "homozygous_effect"
    assert r.status == "direct"
    assert r.matched is True


def test_match_snv_direct_heterozygous():
    r = match_snv(("A", "G"), effect_allele="A", other_allele="G")
    assert r.dosage == 1
    assert r.zygosity == "heterozygous"
    assert r.status == "direct"


def test_match_snv_direct_homozygous_other():
    r = match_snv(("G", "G"), effect_allele="A", other_allele="G")
    assert r.dosage == 0
    assert r.zygosity == "homozygous_other"
    assert r.status == "direct"
    assert r.matched is True


def test_match_snv_missing_on_no_call():
    r = match_snv(("-", "-"), effect_allele="A", other_allele="G")
    assert r.status == "missing"
    assert r.matched is False
    assert r.dosage is None


def test_match_snv_missing_on_indel_marker_in_snv_path():
    r = match_snv(("I", "D"), effect_allele="A", other_allele="G")
    assert r.status == "missing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_genotype_match.py -k match_snv -v`
Expected: FAIL with `ImportError: cannot import name 'match_snv'`.

- [ ] **Step 3: Write minimal implementation**

Append to `analyzers/genotype_match.py`:
```python
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

    return _miss("no_match")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_genotype_match.py -k match_snv -v`
Expected: PASS (5 tests). The two flip/palindromic behaviours come in Task 3.

- [ ] **Step 5: Commit**

```bash
git add analyzers/genotype_match.py tests/test_genotype_match.py
git commit -m "match_snv: direct matching, zygosity, missing/no-call handling"
```

---

## Task 3: `match_snv` — reverse-complement + palindromic safety

**Files:**
- Modify: `analyzers/genotype_match.py`
- Test: `tests/test_genotype_match.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_genotype_match.py`:
```python
def test_match_snv_strand_flipped_heterozygous():
    # Curated effect A / other G; user reported on opposite strand → T / C.
    r = match_snv(("T", "C"), effect_allele="A", other_allele="G")
    assert r.dosage == 1
    assert r.status == "strand_flipped"
    assert r.matched is True


def test_match_snv_strand_flipped_homozygous_effect():
    r = match_snv(("T", "T"), effect_allele="A", other_allele="G")
    assert r.dosage == 2
    assert r.status == "strand_flipped"


def test_match_snv_palindromic_direct_match_still_works():
    # A/T site, user genotype fits directly → still a clean direct call.
    r = match_snv(("A", "T"), effect_allele="A", other_allele="T")
    assert r.dosage == 1
    assert r.status == "direct"


def test_match_snv_palindromic_no_direct_fit_is_flagged_not_flipped():
    # C/G site, user is A/A — a naive flip would call it; we must NOT.
    r = match_snv(("A", "A"), effect_allele="C", other_allele="G")
    assert r.status == "ambiguous_palindromic"
    assert r.matched is False


def test_match_snv_unknown_other_allele_direct_hit():
    r = match_snv(("A", "G"), effect_allele="A")  # other unknown
    assert r.dosage == 1
    assert r.status == "direct"


def test_match_snv_unknown_other_allele_flip_only_when_unambiguous():
    # effect A unknown-other; user T/C: T == rc(A) present, A absent → confident flip.
    r = match_snv(("T", "C"), effect_allele="A")
    assert r.dosage == 1
    assert r.status == "strand_flipped"


def test_match_snv_no_match_on_inconsistent_genotype():
    # A/C is inconsistent with an A/G site (and its T/C flip) → honest no_match.
    r = match_snv(("A", "C"), effect_allele="A", other_allele="G")
    assert r.status == "no_match"
    assert r.matched is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_genotype_match.py -k "strand or palindromic or unknown_other" -v`
Expected: FAIL — current `match_snv` returns `no_match` for flipped/palindromic inputs.

- [ ] **Step 3: Write the implementation**

In `analyzers/genotype_match.py`, replace the body of `match_snv` from the `# Direct` comment to the final `return _miss("no_match")` with:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_genotype_match.py -v`
Expected: PASS (all match_snv + reverse_complement tests).

- [ ] **Step 5: Commit**

```bash
git add analyzers/genotype_match.py tests/test_genotype_match.py
git commit -m "match_snv: reverse-complement matching with palindromic safety"
```

---

## Task 4: `resolve_genotype_key` (for traits)

**Files:**
- Modify: `analyzers/genotype_match.py`
- Test: `tests/test_genotype_match.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_genotype_match.py`:
```python
from analyzers.genotype_match import resolve_genotype_key


def test_resolve_key_direct_ordering():
    key, status = resolve_genotype_key(("A", "G"), ["AA", "AG", "GG"])
    assert key == "AG"
    assert status == "direct"


def test_resolve_key_reversed_ordering():
    key, status = resolve_genotype_key(("G", "A"), ["AA", "AG", "GG"])
    assert key == "AG"
    assert status == "direct"


def test_resolve_key_slash_format():
    key, status = resolve_genotype_key(("C", "T"), ["C/C", "C/T", "T/T"])
    assert key == "C/T"
    assert status == "direct"


def test_resolve_key_strand_flipped():
    # Keys recorded on opposite strand: user A/G should match T/C key set.
    key, status = resolve_genotype_key(("A", "G"), ["TT", "TC", "CC"])
    assert key == "TC"
    assert status == "strand_flipped"


def test_resolve_key_palindromic_heterozygote_not_flipped():
    # User A/T is a palindromic genotype — its reverse-complement is itself, so a flip
    # can't resolve strand. Against an A/G site it has no direct match → flagged, not flipped.
    key, status = resolve_genotype_key(("A", "T"), ["AA", "AG", "GG"])
    assert key is None
    assert status == "ambiguous_palindromic"


def test_resolve_key_no_match():
    key, status = resolve_genotype_key(("A", "A"), ["GG", "GC", "CC"])
    assert key is None
    assert status == "no_match"


def test_resolve_key_missing_on_no_call():
    key, status = resolve_genotype_key(("-", "G"), ["AA", "AG", "GG"])
    assert key is None
    assert status == "missing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_genotype_match.py -k resolve_key -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_genotype_key'`.

- [ ] **Step 3: Write the implementation**

Append to `analyzers/genotype_match.py`:
```python
def _genotype_key_variants(a1: str, a2: str) -> list[str]:
    """All string forms a genotype_results map might use for this allele pair."""
    return [
        f"{a1}/{a2}", f"{a2}/{a1}", "/".join(sorted([a1, a2])),
        f"{a1}{a2}", f"{a2}{a1}", "".join(sorted([a1, a2])),
    ]


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_genotype_match.py -k resolve_key -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add analyzers/genotype_match.py tests/test_genotype_match.py
git commit -m "Add resolve_genotype_key for strand-aware trait lookups"
```

---

## Task 5: `to_reference_strand` (for APOE) + `match_indel`

**Files:**
- Modify: `analyzers/genotype_match.py`
- Test: `tests/test_genotype_match.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_genotype_match.py`:
```python
from analyzers.genotype_match import to_reference_strand, match_indel


def test_to_reference_strand_direct():
    assert to_reference_strand(("C", "T"), "C", "T") == ("C", "T")


def test_to_reference_strand_flips():
    # User reported as G/A on opposite strand of a C/T site → C/T.
    assert to_reference_strand(("G", "A"), "C", "T") == ("C", "T")


def test_to_reference_strand_palindromic_returns_none():
    assert to_reference_strand(("A", "A"), "A", "T") is None


def test_to_reference_strand_no_call_returns_none():
    assert to_reference_strand(("-", "C"), "C", "T") is None


def test_match_indel_deletion_heterozygous():
    r = match_indel(("D", "I"), risk_allele="delAG")
    assert r.dosage == 1
    assert r.status == "direct"


def test_match_indel_insertion_homozygous():
    r = match_indel(("I", "I"), risk_allele="insC")
    assert r.dosage == 2


def test_match_indel_missing_when_not_indel_genotype():
    # Parser currently drops I/D, so SNV bases here mean "no indel call available".
    r = match_indel(("A", "G"), risk_allele="delAG")
    assert r.status == "missing"


def test_match_indel_unrecognized_risk_allele():
    r = match_indel(("D", "D"), risk_allele="A")
    assert r.status == "no_match"


def test_match_indel_dash_risk_allele_is_no_match():
    # '-' is the curated *normal* allele (reference / no-indel), not a risk allele.
    r = match_indel(("I", "I"), risk_allele="-")
    assert r.status == "no_match"


def test_match_snv_palindromic_flip_of_alleles_not_fabricated():
    # A/T site, user C/C: C/C is the complement set of... nothing in {A,T}; a naive
    # flip must not manufacture a call. Stronger probe than the A/A vs C/G case.
    r = match_snv(("C", "C"), effect_allele="A", other_allele="T")
    assert r.status == "ambiguous_palindromic"
    assert r.matched is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_genotype_match.py -k "reference_strand or indel" -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write the implementation**

Append to `analyzers/genotype_match.py`:
```python
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
    if {a1, a2} <= ref:
        return (a1, a2)
    if ref in _PALINDROMES:
        return None
    if {a1, a2} <= {_COMPLEMENT[a], _COMPLEMENT[b]}:
        return (_COMPLEMENT[a1], _COMPLEMENT[a2])
    return None


def match_indel(user_genotype, risk_allele, normal_allele=None) -> MatchResult:
    """Match curated indel risk alleles (insC / delAG / delCTT / '-') against AncestryDNA
    I/D markers. Conservative: flags rather than guesses.

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_genotype_match.py -v`
Expected: PASS (full matcher suite).

- [ ] **Step 5: Commit**

```bash
git add analyzers/genotype_match.py tests/test_genotype_match.py
git commit -m "Add to_reference_strand (APOE) and conservative match_indel"
```

---

## Task 6: Refactor `health_risks.py` to use the matcher

**Files:**
- Modify: `analyzers/health_risks.py:88-97` (curated loop), `:190-202` (ClinVar loop), `:290-291` (APOE reads)
- Test: `tests/test_genotype_match.py` (covered) + integration test in Task 10

- [ ] **Step 1: Write a failing characterization + strand test**

Create `tests/test_health_risks.py`:
```python
from analyzers.health_risks import _analyze_curated_variants


CURATED = [{
    "rsid": "rs1801133", "gene": "MTHFR", "condition": "Homocysteine",
    "risk_allele": "A", "normal_allele": "G", "severity": "MODERATE",
    "odds_ratio": 1.5, "population_frequency": 0.3, "description": "desc",
}]


def test_curated_direct_carrier_found():
    findings = _analyze_curated_variants({"rs1801133": ("A", "G")}, CURATED)
    assert len(findings) == 1
    assert findings[0]["zygosity"] == "heterozygous"


def test_curated_strand_flipped_carrier_found():
    # Same carrier, reported on the opposite strand (T/C). Must still be found.
    findings = _analyze_curated_variants({"rs1801133": ("T", "C")}, CURATED)
    assert len(findings) == 1
    assert findings[0]["zygosity"] == "heterozygous"


def test_curated_non_carrier_not_found():
    findings = _analyze_curated_variants({"rs1801133": ("G", "G")}, CURATED)
    assert findings == []
```

- [ ] **Step 2: Run to verify the strand test fails**

Run: `python -m pytest tests/test_health_risks.py -v`
Expected: `test_curated_strand_flipped_carrier_found` FAILS (current code finds nothing for T/C); the other two PASS.

- [ ] **Step 3: Refactor the curated loop**

In `analyzers/health_risks.py`, add to the imports block (after line 23):
```python
from analyzers.genotype_match import match_snv, match_indel
```
Replace lines 88-99 (from `allele1, allele2 = genotypes[rsid]` through the `zygosity = ...` line) with:
```python
        allele1, allele2 = genotypes[rsid]
        risk_allele = variant.get("risk_allele", "").upper()
        if not risk_allele:
            continue

        normal_allele = variant.get("normal_allele")
        if risk_allele.startswith(("INS", "DEL")) or risk_allele in ("I", "D"):
            match = match_indel((allele1, allele2), risk_allele, normal_allele)
        else:
            match = match_snv((allele1, allele2), risk_allele, normal_allele)

        if not match.matched or not match.dosage:
            continue

        zygosity = "homozygous" if match.dosage == 2 else "heterozygous"
```
The existing finding dict already uses `zygosity`, `allele1`, `allele2`, `risk_allele` — leave it. Add one line to the appended dict (inside the `findings.append({...})`, after `"your_genotype": ...`):
```python
            "match_status": match.status,
```

- [ ] **Step 4: Refactor the ClinVar loop**

First, add `ref_allele` to the ClinVar SELECT so the matcher can detect palindromic sites
(without the reference allele, `match_snv` falls back to its unknown-`other` path, which
*can* flip an A/T or C/G site and fabricate a call — passing `ref_allele` prevents that).
Change the query's column list (around line 179-180) from:
```python
                SELECT rsid, gene, phenotype, clinical_significance,
                       review_status, alt_allele
```
to:
```python
                SELECT rsid, gene, phenotype, clinical_significance,
                       review_status, ref_allele, alt_allele
```
Then replace lines 190-202 (from `allele1, allele2 = genotypes[rsid]` through the
`zygosity = ...` line) with:
```python
                allele1, allele2 = genotypes[rsid]
                risk_allele = (row["alt_allele"] or "").upper()
                ref_allele = (row["ref_allele"] or "").upper() or None
                if not risk_allele:
                    continue

                # Pass ref as other_allele so palindromic (A/T, C/G) ClinVar sites are
                # matched direct-only and never strand-flipped into a fabricated finding.
                match = match_snv((allele1, allele2), risk_allele, other_allele=ref_allele)
                if not match.matched or not match.dosage:
                    continue

                zygosity = "homozygous" if match.dosage == 2 else "heterozygous"
```
Add to that finding dict (after `"your_genotype": ...`):
```python
                    "match_status": match.status,
```
Note: `ref_allele` is a column in the `clinvar` table; if it is empty/NULL for a row, the
matcher degrades to the unknown-`other` path for that row only.

- [ ] **Step 5: Refactor the APOE reads**

In `_analyze_apoe` (line 266+), replace lines 290-291:
```python
    hap1 = _apoe_haplotype(rs429358[0], rs7412[0])
    hap2 = _apoe_haplotype(rs429358[1], rs7412[1])
```
with:
```python
    from analyzers.genotype_match import to_reference_strand
    # Normalise each SNP onto its reference strand (rs429358 C/T, rs7412 C/T) so a
    # strand-flipped array doesn't misread the APOE haplotype.
    rs429358 = to_reference_strand(rs429358, "C", "T") or rs429358
    rs7412 = to_reference_strand(rs7412, "C", "T") or rs7412

    hap1 = _apoe_haplotype(rs429358[0], rs7412[0])
    hap2 = _apoe_haplotype(rs429358[1], rs7412[1])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_health_risks.py -v`
Expected: PASS (3 tests, including the strand-flipped carrier).

- [ ] **Step 7: Commit**

```bash
git add analyzers/health_risks.py tests/test_health_risks.py
git commit -m "health_risks: route matching through strand-aware matcher"
```

---

## Task 7: Refactor `traits.py` to use `resolve_genotype_key`

**Files:**
- Modify: `analyzers/traits.py:77-84` and `_lookup_phenotype` (`:184-212`)
- Test: `tests/test_traits.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_traits.py`:
```python
from analyzers.traits import _analyze_curated_traits


TRAITS = [{
    "rsid": "rs4988235", "gene": "MCM6", "trait": "Lactose tolerance",
    "category": "Nutrition",
    "genotype_results": {"AA": "Tolerant", "AG": "Partial", "GG": "Intolerant"},
    "confidence": "high",
}]


def test_trait_direct_lookup():
    findings = _analyze_curated_traits({"rs4988235": ("A", "G")}, TRAITS)
    assert findings[0]["result"] == "Partial"


def test_trait_strand_flipped_lookup():
    # Opposite strand of A/G is T/C; must resolve to the AG bucket.
    findings = _analyze_curated_traits({"rs4988235": ("T", "C")}, TRAITS)
    assert findings[0]["result"] == "Partial"


def test_trait_homozygous_lookup():
    findings = _analyze_curated_traits({"rs4988235": ("G", "G")}, TRAITS)
    assert findings[0]["result"] == "Intolerant"


def test_trait_indel_lookup():
    indel_trait = [{
        "rsid": "rs1799752", "gene": "ACE", "trait": "ACE I/D",
        "category": "Athletic",
        "genotype_results": {"II": "Endurance", "ID": "Mixed", "DD": "Power"},
        "confidence": "moderate",
    }]
    findings = _analyze_curated_traits({"rs1799752": ("D", "D")}, indel_trait)
    assert findings[0]["result"] == "Power"


def test_trait_no_match_falls_back_to_default():
    variant = [{
        "rsid": "rs4988235", "gene": "MCM6", "trait": "Lactose tolerance",
        "category": "Nutrition",
        "genotype_results": {"AA": "Tolerant", "AG": "Partial", "GG": "Intolerant"},
        "default_phenotype": "Unknown", "confidence": "high",
    }]
    # A/C fits neither the A/G map nor its reverse-complement → genuine no-match → default.
    findings = _analyze_curated_traits({"rs4988235": ("A", "C")}, variant)
    assert findings[0]["result"] == "Unknown"
```

- [ ] **Step 2: Run to verify the strand test fails**

Run: `python -m pytest tests/test_traits.py -v`
Expected: `test_trait_strand_flipped_lookup` FAILS (result falls back to "Typical").

- [ ] **Step 3: Refactor the lookup**

In `analyzers/traits.py`, add after line 17 (the existing imports):
```python
from analyzers.genotype_match import resolve_genotype_key
```
Replace `_make_genotype_key` and `_lookup_phenotype` usage. Specifically, replace lines 78-84:
```python
        genotype_key = _make_genotype_key(allele1, allele2)

        # Look up phenotype — try both "genotype_results" and "phenotype_map" keys
        phenotype_map = variant.get("genotype_results", variant.get("phenotype_map", {}))
        result = _lookup_phenotype(genotype_key, allele1, allele2, phenotype_map)
        if not result:
            result = variant.get("default_phenotype", "Typical")
```
with:
```python
        phenotype_map = variant.get("genotype_results", variant.get("phenotype_map", {}))
        matched_key, _status = resolve_genotype_key((allele1, allele2), list(phenotype_map.keys()))
        if not matched_key:
            # Indel-keyed maps (e.g. ACE I/D: II/ID/DD) use markers the strand-aware
            # resolver doesn't handle; fall back to a direct concat/slash lookup for them.
            for cand in (f"{allele1}{allele2}", f"{allele2}{allele1}",
                         f"{allele1}/{allele2}", f"{allele2}/{allele1}"):
                if cand in phenotype_map:
                    matched_key = cand
                    break
        result = phenotype_map.get(matched_key) if matched_key else None
        genotype_key = matched_key or "/".join(sorted([allele1, allele2]))
        if not result:
            result = variant.get("default_phenotype", "Typical")
```
Then delete the now-unused `_make_genotype_key` (lines 179-181) and `_lookup_phenotype`
(lines 184-212) functions. The `resolve_genotype_key` import only accepts ACGT, so the indel
fallback above preserves the old `_lookup_phenotype`'s I/D concat matching (ACE etc.).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_traits.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add analyzers/traits.py tests/test_traits.py
git commit -m "traits: strand-aware genotype-key resolution"
```

---

## Task 8: Pharmacogenomics honesty stopgap

**Files:**
- Modify: `analyzers/pharmacogenomics.py:104-114` (curated default), `:71-77` (dedup)
- Test: `tests/test_pharmacogenomics.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pharmacogenomics.py`:
```python
from analyzers.pharmacogenomics import _analyze_curated_pharma


# Real-shaped curated entry (no variant_allele / phenotype_map — the actual data shape).
PHARMA = [{
    "rsid": "rs3892097", "gene": "CYP2D6", "star_allele": "*4",
    "effect": "Non-functional", "drugs": ["codeine", "tramadol"],
}]


def test_curated_pharma_does_not_fabricate_normal_metabolizer():
    results = _analyze_curated_pharma({"rs3892097": ("A", "G")}, PHARMA)
    assert len(results) == 1
    # Must NOT claim Normal Metabolizer when it cannot actually call the phenotype.
    assert results[0]["metabolizer_status"] == "Not assessed"
    assert results[0]["metabolizer_code"] == "NA"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_pharmacogenomics.py -v`
Expected: FAIL — current default is "Normal Metabolizer" / "NM".

- [ ] **Step 3: Apply the stopgap**

In `analyzers/pharmacogenomics.py`, change the curated default dict (lines 108-110) from:
```python
                "star_alleles": "*1/*1",  # default reference
                "metabolizer_status": "Normal Metabolizer",
                "metabolizer_code": "NM",
```
to:
```python
                "star_alleles": "Not assessed",
                "metabolizer_status": "Not assessed",
                "metabolizer_code": "NA",
```
This is honest: with the current data, `variant_count` is always 0, so the code never
reaches the real-phenotype branch. (The `phenotype_map`/`drugs` machinery below is left in
place for the Tier 1.5 data reconnection.)

Apply the same change to the **DB path**, which also fabricates a default. In
`_analyze_pharmgkb_db`, change its default dict (lines 204-206) from:
```python
                        "star_alleles": "*1/*1",
                        "metabolizer_status": "Normal Metabolizer",
                        "metabolizer_code": "NM",
```
to:
```python
                        "star_alleles": "Not assessed",
                        "metabolizer_status": "Not assessed",
                        "metabolizer_code": "NA",
```
The DB path never computes a real metabolizer status either (its `variant_count` is
hardcoded to 0), so this default is the honest one. Drug annotations from the DB are still
attached and surfaced.

- [ ] **Step 4: Stop the empty curated stub from displacing DB drugs**

Replace the dedup block (lines 72-77):
```python
    seen_genes = {}
    for r in results:
        gene = r["gene"]
        if gene not in seen_genes:
            seen_genes[gene] = r
    results = list(seen_genes.values())
```
with:
```python
    # Prefer the result that actually carries drug annotations; with the current data the
    # curated path is "Not assessed" with no drugs, so a DB result should win.
    seen_genes = {}
    for r in results:
        gene = r["gene"]
        existing = seen_genes.get(gene)
        if existing is None or (not existing["drugs_affected"] and r["drugs_affected"]):
            seen_genes[gene] = r
    results = list(seen_genes.values())
```

- [ ] **Step 5: Add a test that DB drugs survive, then run**

Append to `tests/test_pharmacogenomics.py`:
```python
from analyzers.pharmacogenomics import analyze_pharmacogenomics


def test_dedup_prefers_result_with_drugs(monkeypatch):
    import analyzers.pharmacogenomics as pg

    curated = [{"gene": "CYP2C19", "tested_variants": [], "star_alleles": "Not assessed",
                "metabolizer_status": "Not assessed", "metabolizer_code": "NA",
                "drugs_affected": [], "is_critical": False, "critical_warning": None}]
    dbres = [{"gene": "CYP2C19", "tested_variants": [], "star_alleles": "*1/*1",
              "metabolizer_status": "Normal Metabolizer", "metabolizer_code": "NM",
              "drugs_affected": [{"drug": "clopidogrel"}], "is_critical": False,
              "critical_warning": None}]
    monkeypatch.setattr(pg, "_analyze_curated_pharma", lambda g, d: curated)
    monkeypatch.setattr(pg, "_analyze_pharmgkb_db", lambda g, d: dbres)

    out = analyze_pharmacogenomics({"rs4244285": ("A", "G")}, "ignored.db")
    cyp = [r for r in out if r["gene"] == "CYP2C19"][0]
    assert cyp["drugs_affected"] == [{"drug": "clopidogrel"}]
```

Run: `python -m pytest tests/test_pharmacogenomics.py -v`
Expected: PASS.

- [ ] **Step 5b: Fix the frontend metabolism chart (end-to-end honesty)**

`static/js/app.js` `renderMetabolismInsight` buckets every non-poor/intermediate/rapid
status into "Normal" (and defaults a missing status to 'Normal') — so "Not assessed" genes
re-appear as Normal Metabolizers in the chart, undoing the backend fix. Add a `notAssessed`
bucket, route `not assessed`/`na`/empty into it (before the other checks), drop the
`|| 'Normal'` default, and add a "Not assessed" bar. (See Unit D implementation for the
exact diff.) Also pin the inert curated path and the DB-path default with tests:
`test_curated_pharma_does_not_fabricate_normal_metabolizer` asserts `drugs_affected == []`;
add `test_dedup_prefers_drugs_when_curated_has_them` and a temp-DB
`test_db_path_not_assessed_default_and_keeps_drug`.

- [ ] **Step 6: Commit**

```bash
git add analyzers/pharmacogenomics.py tests/test_pharmacogenomics.py static/js/app.js
git commit -m "pharma: stop fabricating Normal Metabolizer (backend + chart); keep DB drugs"
```

---

## Task 9: Parser — 23andMe (adaptive columns)

**Files:**
- Modify: `analyzers/parser.py:71-75` (no-header path) and `_default_column_indices`
- Test: `tests/test_parser.py`, `tests/fixtures/`

- [ ] **Step 1: Create fixtures**

Create `tests/fixtures/ancestry_sample.txt`:
```
#AncestryDNA raw data
rsid	chromosome	position	allele1	allele2
rs1801133	1	11856378	A	G
rs4988235	2	136608646	A	A
```
Create `tests/fixtures/23andme_sample.txt`:
```
# This data file generated by 23andMe
# rsid	chromosome	position	genotype
rs1801133	1	11856378	AG
rs4988235	2	136608646	AA
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_parser.py`:
```python
import io
from analyzers.parser import parse_ancestry_file


def _read(path):
    with open(path) as f:
        return io.StringIO(f.read())


def test_parse_ancestry_format():
    g = parse_ancestry_file(_read("tests/fixtures/ancestry_sample.txt"))
    assert g["rs1801133"] == ("A", "G")
    assert g["rs4988235"] == ("A", "A")


def test_parse_23andme_format():
    g = parse_ancestry_file(_read("tests/fixtures/23andme_sample.txt"))
    assert g["rs1801133"] == ("A", "G")
    assert g["rs4988235"] == ("A", "A")


def test_parse_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_ancestry_file(io.StringIO("# only comments\n"))
```

- [ ] **Step 3: Run to verify 23andMe test fails**

Run: `python -m pytest tests/test_parser.py -v`
Expected: `test_parse_23andme_format` FAILS (no valid genotypes — 4-col layout misread as 5-col AncestryDNA); the other two PASS.

- [ ] **Step 4: Make default columns adaptive**

In `analyzers/parser.py`, the no-header branch (lines 71-75) currently always assumes the 5-column AncestryDNA layout. Replace lines 72-75:
```python
            if line.lower().startswith("rs"):
                col_indices = _default_column_indices()
                header_found = True
                # Fall through to parse this line as data
```
with:
```python
            if line.lower().startswith("rs"):
                col_indices = _infer_columns_from_data(line)
                header_found = True
                # Fall through to parse this line as data
```
Add a new function next to `_default_column_indices` (after line 165):
```python
def _infer_columns_from_data(line: str) -> Dict[str, int]:
    """Infer column layout from the first data row when there is no detectable header.

    AncestryDNA: rsid, chromosome, position, allele1, allele2 (5 cols, split alleles).
    23andMe:     rsid, chromosome, position, genotype       (4 cols, combined genotype).
    """
    for delimiter in ("\t", ","):
        fields = line.split(delimiter)
        if len(fields) >= 5:
            return {"rsid": 0, "chromosome": 1, "position": 2, "allele1": 3, "allele2": 4}
        if len(fields) == 4:
            return {"rsid": 0, "chromosome": 1, "position": 2, "genotype": 3}
    return _default_column_indices()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_parser.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add analyzers/parser.py tests/test_parser.py tests/fixtures/ancestry_sample.txt tests/fixtures/23andme_sample.txt
git commit -m "parser: infer 4-column 23andMe vs 5-column AncestryDNA layout"
```

---

## Task 10: In-memory zip handling + app wiring

**Files:**
- Modify: `analyzers/parser.py` (new `read_genotype_text`), `app.py:47-58`
- Test: `tests/test_parser.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parser.py`:
```python
import zipfile


def test_zip_unwrap_returns_text(tmp_path):
    from analyzers.parser import read_genotype_text

    with open("tests/fixtures/23andme_sample.txt", "rb") as f:
        inner = f.read()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("genome.txt", inner)
    text = read_genotype_text(buf.getvalue(), "genome.zip")
    assert "rs1801133" in text


def test_read_genotype_text_plain_passthrough():
    from analyzers.parser import read_genotype_text
    raw = b"rs1\t1\t1\tA\tG\n"
    assert read_genotype_text(raw, "x.txt") == "rs1\t1\t1\tA\tG\n"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_parser.py -k "zip or passthrough" -v`
Expected: FAIL with `ImportError: cannot import name 'read_genotype_text'`.

- [ ] **Step 3: Implement the in-memory reader**

In `analyzers/parser.py`, add `import zipfile` at the top (after `import io`), and add:
```python
def read_genotype_text(raw_bytes: bytes, filename: str) -> str:
    """Decode uploaded bytes to text, transparently unwrapping a .zip in memory.

    23andMe (and others) export a zipped single text file. Everything stays in memory —
    nothing is written to disk, preserving the app's privacy guarantee.
    """
    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            data_members = [n for n in z.namelist() if not n.endswith("/")]
            if not data_members:
                raise ValueError("Zip archive is empty.")
            # Prefer a text-like member; fall back to the first.
            member = next(
                (n for n in data_members if n.lower().endswith((".txt", ".csv", ".tsv"))),
                data_members[0],
            )
            raw_bytes = z.read(member)
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1")
```

- [ ] **Step 4: Run the parser tests**

Run: `python -m pytest tests/test_parser.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Wire it into `app.py`**

In `app.py`, replace lines 47-58 (the read/decode/parse block) with:
```python
    try:
        from analyzers.parser import read_genotype_text

        raw_content = file.read()
        text_content = read_genotype_text(raw_content, file.filename)

        file_obj = io.StringIO(text_content)

        # Parse the DNA data file
        genotypes = parse_ancestry_file(file_obj)
```
Leave the rest of the `try` block (the `if not genotypes:` check onward) unchanged. The
bare `decode` lines are now handled inside `read_genotype_text`.

- [ ] **Step 6: Sanity-check the app imports**

Run: `python -c "import app; print('ok')"`
Expected: prints `ok` (no import or syntax errors).

- [ ] **Step 7: Commit**

```bash
git add analyzers/parser.py app.py tests/test_parser.py
git commit -m "parser+app: in-memory zip unwrapping for 23andMe uploads"
```

---

## Task 11: Integration regression test (the proof)

**Files:**
- Test: `tests/test_analyzers_integration.py`

- [ ] **Step 1: Write the regression test**

This covers the seams the matcher's own unit tests can't reach: the curated loop, the
ClinVar loop (incl. its `ref_allele` palindrome plumbing — the subtlest line in Unit B),
and the APOE strand normalization.

Create `tests/test_analyzers_integration.py`:
```python
"""Tier 1 integration regression tests: strand correctness must hold end-to-end through the
analyzers, not only in the matcher's unit tests. The headline case — a reverse-complement
carrier surfacing the same finding as a forward-strand carrier — is the bug Tier 1 fixes."""
import sqlite3

import pytest

from analyzers.health_risks import (
    _analyze_apoe,
    _analyze_clinvar,
    _analyze_curated_variants,
)
from config import PATHOGENIC_SIGNIFICANCES


PATHOGENIC = [{
    "rsid": "rs80357906", "gene": "BRCA1", "condition": "Hereditary breast cancer",
    "risk_allele": "C", "normal_allele": "T", "severity": "HIGH",
    "odds_ratio": 5.0, "population_frequency": 0.001, "description": "BRCA1 variant",
}]


def test_forward_and_reverse_strand_carriers_match():
    forward = _analyze_curated_variants({"rs80357906": ("C", "T")}, PATHOGENIC)
    reverse = _analyze_curated_variants({"rs80357906": ("G", "A")}, PATHOGENIC)  # rc of C/T
    assert len(forward) == 1
    assert len(reverse) == 1
    assert forward[0]["gene"] == reverse[0]["gene"] == "BRCA1"
    assert forward[0]["zygosity"] == reverse[0]["zygosity"] == "heterozygous"
    assert reverse[0]["match_status"] == "strand_flipped"


def test_curated_homozygous_carrier():
    out = _analyze_curated_variants({"rs80357906": ("C", "C")}, PATHOGENIC)
    assert len(out) == 1
    assert out[0]["zygosity"] == "homozygous"


def test_palindromic_carrier_not_fabricated():
    palindromic = [{
        "rsid": "rs1", "gene": "X", "condition": "Y", "risk_allele": "A",
        "normal_allele": "T", "severity": "MODERATE", "odds_ratio": 1.2,
        "population_frequency": 0.1, "description": "d",
    }]
    # User C/C can't be a strand-resolved call at an A/T site → no fabricated finding.
    out = _analyze_curated_variants({"rs1": ("C", "C")}, palindromic)
    assert out == []


def test_curated_indel_routing():
    indel = [{
        "rsid": "rs_indel", "gene": "BRCA1", "condition": "Hereditary breast cancer",
        "risk_allele": "delAG", "normal_allele": "-", "severity": "HIGH",
        "odds_ratio": 5.0, "population_frequency": 0.001, "description": "d",
    }]
    # AncestryDNA reports indels as I/D; feed that directly to prove the routing branch.
    out = _analyze_curated_variants({"rs_indel": ("D", "I")}, indel)
    assert len(out) == 1
    assert out[0]["zygosity"] == "heterozygous"


def test_apoe_strand_flipped_e4_is_normalized():
    # ε4/ε4 is rs429358=C/C, rs7412=C/C; on the opposite strand that's G/G, G/G.
    # to_reference_strand must normalize it back so the ε4/ε4 call still fires.
    flipped = _analyze_apoe({"rs429358": ("G", "G"), "rs7412": ("G", "G")})
    assert flipped is not None
    assert flipped["zygosity"] == "ε4/ε4"
    assert flipped["severity"] == "HIGH"


@pytest.fixture
def clinvar_db(tmp_path):
    db = tmp_path / "ref.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE clinvar (rsid TEXT, gene TEXT, clinical_significance TEXT, "
        "phenotype TEXT, chromosome TEXT, position INTEGER, ref_allele TEXT, "
        "alt_allele TEXT, review_status TEXT)"
    )
    sig = PATHOGENIC_SIGNIFICANCES[0]
    con.executemany(
        "INSERT INTO clinvar VALUES (?,?,?,?,?,?,?,?,?)",
        [
            # non-palindromic C/T site (ref C, alt T)
            ("rs_np", "GENE1", sig, "Cond1", "1", 100, "C", "T", "reviewed by expert panel"),
            # palindromic A/T site (ref A, alt T)
            ("rs_pal", "GENE2", sig, "Cond2", "2", 200, "A", "T", "reviewed by expert panel"),
        ],
    )
    con.commit()
    con.close()
    return str(db)


def test_clinvar_strand_flipped_carrier_surfaces(clinvar_db):
    # alt=T at a C/T site; a carrier reported on the opposite strand is A/G (rc of T/C).
    findings = _analyze_clinvar({"rs_np": ("A", "G")}, clinvar_db)
    assert len(findings) == 1
    assert findings[0]["match_status"] == "strand_flipped"


def test_clinvar_palindromic_not_fabricated(clinvar_db):
    # A/T site (ref A, alt T): user C/C can't be strand-resolved → must not fabricate.
    findings = _analyze_clinvar({"rs_pal": ("C", "C")}, clinvar_db)
    assert findings == []
```

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: PASS — all tests across every test file.

- [ ] **Step 3: Commit**

```bash
git add tests/test_analyzers_integration.py
git commit -m "Add strand-flip regression + ClinVar/APOE/indel integration tests"
```

---

## Task 12: Full-suite green + spec close-out

**Files:**
- Modify: `README.md` (Current state section — formats + pharma honesty note)

- [ ] **Step 1: Run the entire suite once more**

Run: `python -m pytest tests/ -v`
Expected: all green.

- [ ] **Step 2: Update README current state**

In `README.md`, under "Rougher edges" / "No support for 23andMe...", change the 23andMe
line to note 23andMe (txt + zip) is now supported, and add a line that the curated
pharmacogenomics metabolizer call is being reconnected (Tier 1.5) and currently reports
"Not assessed" rather than a default. Keep it factual and brief.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "README: note 23andMe support and pharma honesty stopgap"
```

---

## Self-Review Notes

- **Spec coverage:** matcher (Tasks 1-5), health refactor + strand fix (Task 6), traits
  (Task 7), pharma stopgap (Task 8), 23andMe (Task 9), zip (Task 10), regression test
  (Task 11), README/close-out (Task 12). All spec success criteria map to a task.
- **Type consistency:** `MatchResult(dosage, zygosity, status, matched)` is used uniformly;
  `match_snv`/`match_indel` return it, `resolve_genotype_key`/`to_reference_strand` return
  their own documented shapes. `_hit`/`_miss` helpers keep construction consistent.
- **No real genetic data:** all fixtures are synthetic single-digit-SNP files.
- **Known limitation documented:** `match_indel` is not yet live because the parser drops
  I/D (Task 5 docstring + spec). Intentional, not a gap.
