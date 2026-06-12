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
    assert forward[0]["match_status"] == "direct"


def test_curated_homozygous_carrier():
    out = _analyze_curated_variants({"rs80357906": ("C", "C")}, PATHOGENIC)
    assert len(out) == 1
    assert out[0]["zygosity"] == "homozygous"
    assert out[0]["match_status"] == "direct"


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
    assert out[0]["match_status"] == "direct"


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
            ("rs_np", "GENE1", sig, "Cond1", "1", 100, "C", "T", "reviewed by expert panel"),
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


def test_strand_flipped_homozygous_carrier():
    # G/G is the reverse-complement of C/C; a homozygous risk carrier on the opposite
    # strand must surface as homozygous (dosage 2), not be dropped.
    out = _analyze_curated_variants({"rs80357906": ("G", "G")}, PATHOGENIC)
    assert len(out) == 1
    assert out[0]["zygosity"] == "homozygous"
    assert out[0]["match_status"] == "strand_flipped"


def test_apoe_strand_flipped_mixed_e3_e4():
    # ε3/ε4: forward rs429358=T/C, rs7412=C/C. On the opposite strand: rs429358=A/G,
    # rs7412=G/G. Per-allele normalization must still yield ε3/ε4 (not ε?).
    flipped = _analyze_apoe({"rs429358": ("A", "G"), "rs7412": ("G", "G")})
    assert flipped is not None
    assert flipped["zygosity"] == "ε3/ε4"
    assert flipped["severity"] == "MODERATE"
