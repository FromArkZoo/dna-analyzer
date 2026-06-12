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


import sqlite3

import pytest


@pytest.fixture
def traits_db(tmp_path):
    db = tmp_path / "ref.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE traits (rsid TEXT, category TEXT, name TEXT, gene TEXT, "
        "risk_allele TEXT, effect TEXT, population_frequency REAL)"
    )
    con.execute(
        "INSERT INTO traits VALUES ('rs_t','Physical','Eye color','OCA2','A','Brown',0.5)"
    )
    con.commit()
    con.close()
    return str(db)


def test_db_trait_strand_flipped_surfaces(traits_db):
    from analyzers.traits import _analyze_trait_db
    # risk allele A; user reported on the opposite strand as T/T (rc of A/A). Old naive
    # equality dropped it; the matcher must now surface it as strand_flipped.
    out = _analyze_trait_db({"rs_t": ("T", "T")}, traits_db)
    assert len(out) == 1
    assert out[0]["match_status"] == "strand_flipped"


def test_db_trait_direct_surfaces(traits_db):
    from analyzers.traits import _analyze_trait_db
    out = _analyze_trait_db({"rs_t": ("A", "A")}, traits_db)
    assert len(out) == 1
    assert out[0]["match_status"] == "direct"
