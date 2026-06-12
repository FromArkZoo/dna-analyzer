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
