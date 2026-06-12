from analyzers.pharmacogenomics import _analyze_curated_pharma, analyze_pharmacogenomics


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
    assert results[0]["drugs_affected"] == []  # curated path is inert until Tier 1.5


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


import sqlite3

import pytest


def test_dedup_prefers_drugs_when_curated_has_them(monkeypatch):
    # The other arrangement: curated carries the drugs, DB is the empty stub.
    import analyzers.pharmacogenomics as pg
    curated = [{"gene": "CYP2C19", "tested_variants": [], "star_alleles": "*1/*1",
                "metabolizer_status": "Normal Metabolizer", "metabolizer_code": "NM",
                "drugs_affected": [{"drug": "clopidogrel"}], "is_critical": False,
                "critical_warning": None}]
    dbres = [{"gene": "CYP2C19", "tested_variants": [], "star_alleles": "Not assessed",
              "metabolizer_status": "Not assessed", "metabolizer_code": "NA",
              "drugs_affected": [], "is_critical": False, "critical_warning": None}]
    monkeypatch.setattr(pg, "_analyze_curated_pharma", lambda g, d: curated)
    monkeypatch.setattr(pg, "_analyze_pharmgkb_db", lambda g, d: dbres)
    out = pg.analyze_pharmacogenomics({"rs1": ("A", "G")}, "ignored.db")
    cyp = [r for r in out if r["gene"] == "CYP2C19"][0]
    assert cyp["drugs_affected"] == [{"drug": "clopidogrel"}]


@pytest.fixture
def pharmgkb_db(tmp_path):
    db = tmp_path / "ref.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE pharmgkb (rsid TEXT, gene TEXT, drug TEXT, "
                "phenotype_category TEXT, evidence_level TEXT, annotation_id TEXT)")
    con.execute("CREATE TABLE pharmgkb_alleles (annotation_id TEXT, genotype TEXT, "
                "annotation_text TEXT, allele_function TEXT)")
    con.execute("INSERT INTO pharmgkb VALUES "
                "('rs4244285','CYP2C19','clopidogrel','Efficacy','1A','ann1')")
    con.commit()
    con.close()
    return str(db)


def test_db_path_not_assessed_default_and_keeps_drug(pharmgkb_db):
    from analyzers.pharmacogenomics import _analyze_pharmgkb_db
    results = _analyze_pharmgkb_db({"rs4244285": ("A", "G")}, pharmgkb_db)
    cyp = [r for r in results if r["gene"] == "CYP2C19"][0]
    assert cyp["metabolizer_status"] == "Not assessed"
    assert cyp["metabolizer_code"] == "NA"
    assert any(d["drug"] == "clopidogrel" for d in cyp["drugs_affected"])
