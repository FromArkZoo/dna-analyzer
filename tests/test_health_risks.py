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
