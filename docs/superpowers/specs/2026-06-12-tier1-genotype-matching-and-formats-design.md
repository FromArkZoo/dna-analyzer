# Tier 1: Strand-aware genotype matching, format support, and test harness

**Date:** 2026-06-12
**Status:** Approved (design); pending spec review
**Branch:** `tier1-genotype-matching`

## Goal

Harden the *correctness foundation* of dna-analyzer so a knowledgeable person can trust
its findings. Three pieces, in priority order:

1. A shared **strand-aware genotype-matching module** that every diploid analyzer uses.
2. Real **multi-format support** (23andMe txt + zip alongside AncestryDNA; fix the
   already-accepted-but-broken `.zip` path).
3. A **pytest test harness**, including the regression test that proves the strand bug
   is fixed.

This is Tier 1 of a larger "path to S-class" roadmap. It deliberately does **not** touch
the reference-DB build, ancestry/haplogroup science, PRS calibration, or the frontend.

## The bug this fixes

Every diploid analyzer matches alleles by direct string equality and drops a finding when
the risk-allele count is zero:

- `analyzers/health_risks.py:93-96` and `:196-199` — `risk_count == 0` → `continue`.
- `analyzers/pharmacogenomics.py:~118-120` — same direct-count pattern.
- `analyzers/traits.py:~179-206` — looks up a genotype key against `genotype_results`,
  trying several string orderings but never the reverse-complement.

AncestryDNA (and other arrays) report genotypes on a specific DNA strand. When a curated
`risk_allele` is recorded on the **opposite** strand from how the array reports it, direct
equality fails, `risk_count == 0`, and a genuine carrier is silently treated as a
non-carrier. This is the single highest-risk correctness defect in the codebase: a false
"all clear" on a health finding.

The fix is to centralise matching in one module that tries the reverse-complement when a
direct match fails — *except* for palindromic SNPs, where a flip can't be disambiguated
and would risk fabricating a call (see decision D2).

### Second defect found during planning: pharma analyzer/data drift

`pharma_variants.json` (85 entries, reworked 2026-06-08) carries `star_allele` and a flat
`drugs` string-list. `pharmacogenomics.py` (last touched 2026-04-10) still reads
`variant_allele` and `phenotype_map` fields that **no entry has**. Result:
`variant_count` is always 0, the curated metabolizer status is hardcoded to
"Normal Metabolizer / *1/*1" for every pharmacogene the user carries, no curated drugs
attach, and (because curated wins dedup) DB drugs for the same gene are discarded. The app
currently shows a *falsely reassuring* "Normal Metabolizer" regardless of genotype.

This is analyzer/data drift, not a strand bug, and it cannot be fixed by routing through
the matcher because the data holds no allele to match against. Per decision D5, Tier 1
applies an **honesty stopgap** only; the full reconnection is a separate validated
follow-up (see "Tier 1.5 follow-up").

## Scope

### In scope
- New module `analyzers/genotype_match.py`.
- Refactor `health_risks.py` (curated + ClinVar + APOE) and `traits.py` to use it.
- `pharmacogenomics.py` **honesty stopgap only** (stop fabricating "Normal Metabolizer";
  show "not assessed" for the curated path — see D5).
- 23andMe parsing + in-memory `.zip` handling.
- `tests/` directory with pytest; `pytest` as a dev dependency.

### Out of scope (deliberately)
- **Full pharma reconnection** — re-authoring `pharma_variants.json` with defining alleles
  + phenotype maps and wiring it through the matcher. Deferred to Tier 1.5 (needs data
  authoring + validation, not just a refactor).
- `analyzers/ancestry.py` — the AIM path already handles strand correctly
  (`ancestry.py:244-273`); haplogroup placement is a Tier 2/3 science issue, not a strand
  bug. Untouched to keep the blast radius small.
- VCF / MyHeritage / FamilyTreeDNA formats (deferred to a later tier).
- Reference DB build, PRS calibration, frontend, export.

## Decisions

- **D1 — Formats:** Add 23andMe (txt + zip) only. AncestryDNA stays the primary format.
- **D2 — Palindromic SNPs (A/T, C/G):** Direct-match only; never reverse-complement them.
  Tag as `ambiguous_palindromic` when a direct match doesn't fit. Safest posture — zero
  fabricated flips on health findings, at the cost of missing the rare genuinely-flipped
  palindromic call. Honest uncertainty over a confident guess.
- **D3 — TDD:** Tests are written before the matcher implementation and before the
  analyzer refactor; the refactor must keep the suite green.
- **D4 — Privacy preserved:** Zip handling reads from `io.BytesIO` in memory and never
  writes to disk, consistent with the existing in-memory upload contract.
- **D5 — Pharma honesty stopgap:** The curated pharma path is structurally dead (see above).
  Tier 1 makes it *honest* rather than fixing it: the curated metabolizer status becomes
  "Not assessed" (not a fabricated "Normal Metabolizer"), and DB-sourced drugs are no longer
  discarded by an empty curated result. Real star-allele calling is Tier 1.5.

## Component 1 — `analyzers/genotype_match.py`

A pure, dependency-free module (stdlib only). No DB access, no I/O.

### Public API

```python
@dataclass(frozen=True)
class MatchResult:
    dosage: int | None      # copies of the effect/risk allele: 0, 1, 2, or None if no call
    zygosity: str | None    # "homozygous_effect" | "heterozygous" | "homozygous_other" | None
    status: str             # "direct" | "strand_flipped" | "ambiguous_palindromic"
                            #   | "no_match" | "missing"
    matched: bool           # True iff a confident dosage call was made

def match_snv(
    user_genotype: tuple[str, str],
    effect_allele: str,
    other_allele: str | None = None,
) -> MatchResult: ...

def resolve_genotype_key(
    user_genotype: tuple[str, str],
    known_keys: list[str],
) -> tuple[str | None, str]:    # (matched_key, status) — status as above
    """Strand-aware resolution of a user genotype to one of a set of known genotype-string
    keys (e.g. traits.py 'AA'/'AC'/'CC'). Tries direct orderings, then reverse-complement
    unless the genotype is palindromic."""

def match_indel(
    user_genotype: tuple[str, str],
    risk_allele: str,           # curated form: 'insC', 'delAG', 'delCTT', or '-'
    normal_allele: str | None = None,
) -> MatchResult:
    """Conservative indel matching. Maps curated ins*/del*/'-' to AncestryDNA I/D/no-call.
    Flags (status='no_match' / 'missing') rather than guessing when the array
    representation is unclear or the marker isn't carried."""
```

### `match_snv` resolution order

1. **Normalise:** uppercase, strip whitespace. Treat `-`, `--`, `0`, `00`, `.`, `NN`, and
   empty as no-calls.
2. **Missing:** if either user allele is a no-call (or the genotype is absent upstream) →
   `MatchResult(None, None, "missing", False)`.
3. **Palindromic test:** if `other_allele` is known and `{effect, other}` ∈ `{ {A,T}, {C,G} }`,
   the site is palindromic. Attempt **direct only**:
   - both user alleles ∈ `{effect, other}` → count `effect` → `direct`.
   - else → `ambiguous_palindromic`, `matched=False`.
4. **Non-palindromic:**
   - **Direct:** if both user alleles ∈ `{effect, other}` (or, when `other` unknown, the
     effect allele is present) → count `effect` copies → `direct`.
   - **Reverse-complement:** if direct fails and both user alleles ∈ `{rc(effect), rc(other)}`
     → count `rc(effect)` copies → `strand_flipped`.
   - else → `no_match`.
5. **Unknown `other_allele` degradation:** a direct effect-allele hit (count ≥ 1) is
   reported. A reverse-complement flip is attempted only when it is unambiguous (the user
   alleles are explained by `rc(effect)` and are *not* already valid bases for a different
   plausible call). When ambiguous, prefer `no_match` over a guess.

### `zygosity` mapping
`dosage` 2 → `homozygous_effect`; 1 → `heterozygous`; 0 → `homozygous_other`;
None → None.

## Component 2 — analyzer refactor

Replace ad-hoc matching with calls to the matcher. Each analyzer keeps its own
severity/phenotype logic; only the allele-counting step changes.

- **`health_risks.py`** — both the curated loop (`:88-96`) and the ClinVar loop
  (`:190-199`) call `match_snv(...)`. When `status` is `missing`/`no_match`/`ambiguous_palindromic`,
  behave as today (skip), but the result's `status` is retained on the finding dict for the
  future trust layer. A `strand_flipped` match now correctly *surfaces* a finding that is
  silently dropped today. Indel-style curated risk alleles (`insC`, `delAG`, `-`, …) route
  to `match_indel`.
- **`pharmacogenomics.py`** — **honesty stopgap only** (D5). The curated path stops
  defaulting to "Normal Metabolizer / *1/*1" and instead reports "Not assessed" for the
  metabolizer status when it cannot make a real call (which, with the current data, is
  always). The dedup is adjusted so a DB result with real drug annotations is not displaced
  by an empty curated stub. No matcher routing here until the data is re-authored.
- **`traits.py`** — genotype-key lookup (`:~179-206`) goes through `resolve_genotype_key`,
  adding strand-flipped key resolution while preserving the existing ordering fallbacks.

APOE haplotype calling (`health_risks.py:281+`, rs429358/rs7412) keeps its bespoke logic
but its two single-SNP reads route through `match_snv` for consistency.

## Component 3 — formats

- **`analyzers/parser.py`** — add 23andMe detection: comment lines prefixed `#`, a
  combined two-character genotype column (`AA`, `AG`, `--`). Reuse the existing flexible
  column detection. AncestryDNA parsing is unchanged.
- **Zip handling** — a small helper (`parser.read_text_stream(raw_bytes, filename)` or
  equivalent) that, when the upload is a `.zip`, opens it via `zipfile.ZipFile(io.BytesIO(...))`,
  selects the single data member, and returns a text stream — all in memory. `app.py` calls
  this before `parse_ancestry_file`. No disk writes.

## Component 4 — tests (`tests/`, pytest)

- **`test_genotype_match.py`** — every `match_snv` branch: direct hom/het/hom-other,
  strand-flipped hom/het, palindromic-ambiguous, missing/no-call, unknown-`other` degradation,
  indel ins/del/`-` ↔ I/D, and `resolve_genotype_key` direct + flipped + palindromic.
- **`test_parser.py`** — AncestryDNA fixture, 23andMe txt fixture, 23andMe zip fixture,
  malformed/empty input, no-call filtering, column-alias detection.
- **`test_analyzers_integration.py`** — **the regression test**: a synthetic genotype dict
  carrying a known pathogenic SNV is analysed twice — once forward, once reverse-complemented
  — and must yield the *same* health finding. Plus a palindromic carrier asserting it is
  *not* fabricated (surfaces as ambiguous, not a confident call).
- **Fixtures** — tiny synthetic raw files (a handful of SNPs) under `tests/fixtures/`. No
  real genetic data enters the repo.
- `pytest` added to a dev dependency list (`requirements-dev.txt` or a `[dev]` extra).

## Tier 1.5 follow-up (out of scope here, recorded so it isn't lost)

Reconnect pharmacogenomics properly:
1. Add a `defining_allele` (the SNV allele that tags the star allele) and a het/hom
   `phenotype` mapping to each of the 85 `pharma_variants.json` entries.
2. Validate those defining alleles against PharmVar / PharmGKB / CPIC star-allele
   definitions (mirroring the existing `scripts/validate_*` discipline).
3. Update `pharmacogenomics.py` to route through `match_snv` (already strand-ready) and
   compute real metabolizer status.
4. Add pharma tests with known star-allele carriers, incl. strand-flipped.

## Success criteria

1. A reverse-complement carrier of a known pathogenic SNV produces the same finding as the
   forward-strand carrier (regression test passes).
2. A palindromic A/T or C/G genotype that doesn't directly match is flagged
   `ambiguous_palindromic`, never a fabricated flip.
3. A 23andMe file (txt and zipped) parses to the same genotype dict shape as AncestryDNA.
4. The curated pharma path no longer reports a fabricated "Normal Metabolizer"; it reports
   "Not assessed", and DB drug annotations survive.
5. Health and traits output is unchanged on the existing AncestryDNA happy path where direct
   matching already worked (no regressions).
6. `pytest` runs green; no real genetic data in the repo.

## Risks & mitigations

- **Refactor regressions in 3 analyzers** → TDD; characterise current happy-path output
  first, keep it green.
- **Indel representation is genuinely ambiguous** on consumer arrays (many classic indels
  aren't even on the chip) → `match_indel` is conservative and flags rather than guesses;
  this is documented behaviour, not silent.
- **Unknown-`other_allele` ClinVar findings** weaken flip confidence → degrade to `no_match`
  rather than risk a wrong flip; revisit when the reference build can supply ref/alt.
