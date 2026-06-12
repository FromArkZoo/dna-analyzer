from analyzers.genotype_match import (
    complement_base,
    match_indel,
    match_snv,
    resolve_genotype_key,
    to_reference_strand,
)


def test_complement_base_basic():
    assert complement_base("A") == "T"
    assert complement_base("T") == "A"
    assert complement_base("C") == "G"
    assert complement_base("G") == "C"


def test_complement_base_lowercase_and_whitespace():
    assert complement_base(" a ") == "T"


def test_complement_base_non_base_returns_none():
    assert complement_base("I") is None
    assert complement_base("") is None
    assert complement_base(None) is None


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


def test_match_snv_strand_flipped_heterozygous():
    r = match_snv(("T", "C"), effect_allele="A", other_allele="G")
    assert r.dosage == 1
    assert r.status == "strand_flipped"
    assert r.matched is True


def test_match_snv_strand_flipped_homozygous_effect():
    r = match_snv(("T", "T"), effect_allele="A", other_allele="G")
    assert r.dosage == 2
    assert r.status == "strand_flipped"


def test_match_snv_palindromic_direct_match_still_works():
    r = match_snv(("A", "T"), effect_allele="A", other_allele="T")
    assert r.dosage == 1
    assert r.status == "direct"


def test_match_snv_palindromic_no_direct_fit_is_flagged_not_flipped():
    r = match_snv(("A", "A"), effect_allele="C", other_allele="G")
    assert r.status == "ambiguous_palindromic"
    assert r.matched is False


def test_match_snv_unknown_other_allele_direct_hit():
    r = match_snv(("A", "G"), effect_allele="A")
    assert r.dosage == 1
    assert r.status == "direct"


def test_match_snv_unknown_other_allele_flip_only_when_unambiguous():
    r = match_snv(("T", "C"), effect_allele="A")
    assert r.dosage == 1
    assert r.status == "strand_flipped"


def test_match_snv_no_match_on_inconsistent_genotype():
    r = match_snv(("A", "C"), effect_allele="A", other_allele="G")
    assert r.status == "no_match"
    assert r.matched is False


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


def test_to_reference_strand_direct():
    assert to_reference_strand(("C", "T"), "C", "T") == ("C", "T")


def test_to_reference_strand_flips():
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
    # A/T site, user C/C: a naive flip must not manufacture a call.
    r = match_snv(("C", "C"), effect_allele="A", other_allele="T")
    assert r.status == "ambiguous_palindromic"
    assert r.matched is False
