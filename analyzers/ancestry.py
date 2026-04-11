"""Ancestry analysis module.

Determines maternal/paternal haplogroups and estimates continental ancestry composition
from ancestry-informative markers.
"""

import json
import os
import sqlite3
from typing import Dict, Optional, Tuple

from config import CURATED_DIR

# Reference populations for ancestry-informative markers.
# European sub-populations use 1000 Genomes codes: GBR, CEU (NW Europe), TSI (S. Europe), FIN.
CONTINENTAL_POPS = [
    "British & Irish",
    "NW European",
    "Southern European",
    "Scandinavian & Finnish",
    "Eastern European",
    "West African",
    "East African",
    "East Asian",
    "South Asian",
    "Americas",
]


def analyze_ancestry(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> dict:
    """Run ancestry analysis: haplogroups + continental composition estimate.

    Args:
        genotypes: Dict of rsid → (allele1, allele2).
        db_path: Path to the reference SQLite database.

    Returns:
        Dict with maternal_haplogroup, paternal_haplogroup, ancestry_composition, caveats.
    """
    result = {
        "maternal_haplogroup": _determine_maternal_haplogroup(genotypes, db_path),
        "paternal_haplogroup": _determine_paternal_haplogroup(genotypes, db_path),
        "composition": _estimate_ancestry_composition(genotypes, db_path),
        "caveats": [
            "Ancestry estimates are approximate and based on a limited set of markers.",
            "Haplogroup assignments trace only one maternal or paternal lineage and do not represent your full ancestry.",
            "Continental categories are simplifications — human genetic variation is continuous, not discrete.",
            "These results should not be used for legal, medical, or identity purposes.",
            "Accuracy depends on the number of ancestry-informative markers available in your data.",
        ],
    }
    return result


def _determine_maternal_haplogroup(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> dict:
    """Determine maternal (mitochondrial) haplogroup from MT chromosome SNPs."""
    # Load haplogroup tree definitions
    curated_path = os.path.join(CURATED_DIR, "haplogroup_tree.json")
    if not os.path.exists(curated_path):
        return {"haplogroup": "Unknown", "description": "Haplogroup data not available."}

    with open(curated_path) as f:
        tree_data = json.load(f)

    mt_tree = tree_data.get("mtdna", [])
    if not mt_tree:
        return {"haplogroup": "Not available", "description": "No mtDNA haplogroup definitions found."}

    # Check if MT chromosome data exists at all
    has_mt = any(rsid.lower().startswith("rs") for rsid in genotypes)  # we'll check against tree
    # Actually check if ANY defining SNPs are present
    all_mt_rsids = set()
    for hg in mt_tree:
        for s in hg.get("defining_snps", []):
            all_mt_rsids.add(s.get("rsid", "").lower())
    not_available_msg = (
        "Your DNA file does not include enough mitochondrial (mtDNA) markers to determine your haplogroup. "
        "This is normal for some AncestryDNA chip versions (like V2.0), which focus on autosomal DNA only. "
        "To get your maternal haplogroup, you could try services like 23andMe, "
        "FamilyTreeDNA, or a dedicated mitochondrial DNA test."
    )

    mt_overlap = sum(1 for r in all_mt_rsids if r in genotypes)
    if mt_overlap < 3:
        return {"haplogroup": "Not available", "description": not_available_msg}

    # Build a lowercase rsid → allele lookup from user genotypes
    user_snps = {}
    for rsid, (a1, a2) in genotypes.items():
        user_snps[rsid.lower()] = a1.upper()  # MT DNA is haploid

    # Score each haplogroup by how many defining SNPs match
    best_match = None
    best_description = ""
    best_score = 0

    for hg in mt_tree:
        defining_snps = hg.get("defining_snps", [])
        if not defining_snps:
            continue

        matched = 0
        tested = 0
        for snp_def in defining_snps:
            rsid = snp_def.get("rsid", "").lower()
            expected = snp_def.get("allele", "").upper()
            if rsid in user_snps:
                tested += 1
                if user_snps[rsid] == expected:
                    matched += 1

        if tested > 0 and matched == tested and matched > best_score:
            best_score = matched
            best_match = hg.get("haplogroup", best_match)
            desc = hg.get("description", "")
            region = hg.get("region", "")
            best_description = f"{desc} Region: {region}." if region else desc

    if not best_match:
        return {"haplogroup": "Not available", "description": not_available_msg}

    return {
        "haplogroup": best_match,
        "description": best_description,
    }


def _determine_paternal_haplogroup(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> Optional[dict]:
    """Determine paternal (Y-chromosome) haplogroup. Returns None for females."""
    curated_path = os.path.join(CURATED_DIR, "haplogroup_tree.json")
    if not os.path.exists(curated_path):
        return None

    with open(curated_path) as f:
        tree_data = json.load(f)

    y_tree = tree_data.get("ydna", [])
    if not y_tree:
        return None

    # Collect all Y-chromosome defining rsids to detect male sex
    y_defining_rsids = set()
    for hg in y_tree:
        for snp_def in hg.get("defining_snps", []):
            y_defining_rsids.add(snp_def.get("rsid", "").lower())

    # Check if any Y-chromosome SNPs are present — indicates male
    user_snps = {}
    for rsid in y_defining_rsids:
        if rsid in genotypes:
            user_snps[rsid] = genotypes[rsid][0].upper()

    if not user_snps:
        # Check if chromosome 23 exists but no Y data — might be female or chip limitation
        return {
            "haplogroup": "Not available",
            "description": "Your DNA file does not include Y-chromosome data. "
                           "This may be because you are female (only males have a Y chromosome), "
                           "or because your DNA chip version does not include Y-chromosome markers."
        }

    # Score each haplogroup
    best_match = "Y-Adam"
    best_description = "Root of Y-chromosome phylogenetic tree."
    best_score = 0

    for hg in y_tree:
        defining_snps = hg.get("defining_snps", [])
        if not defining_snps:
            continue

        matched = 0
        tested = 0
        for snp_def in defining_snps:
            rsid = snp_def.get("rsid", "").lower()
            expected = snp_def.get("allele", "").upper()
            if rsid in user_snps:
                tested += 1
                if user_snps[rsid] == expected:
                    matched += 1

        if tested > 0 and matched == tested and matched > best_score:
            best_score = matched
            best_match = hg.get("haplogroup", best_match)
            desc = hg.get("description", "")
            region = hg.get("region", "")
            best_description = f"{desc} Region: {region}." if region else desc

    return {
        "haplogroup": best_match,
        "description": best_description,
    }


def _estimate_ancestry_composition(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> list[dict]:
    """Estimate continental ancestry using ancestry-informative markers (AIMs).

    Uses a simplified frequency-based method comparing user alleles against
    continental reference frequencies.
    """
    # Load ancestry-informative markers
    curated_path = os.path.join(CURATED_DIR, "ancestry_markers.json")
    if not os.path.exists(curated_path):
        return _default_composition("Ancestry marker data not available.")

    with open(curated_path) as f:
        aim_markers = json.load(f)

    if not aim_markers:
        return _default_composition("No ancestry-informative markers defined.")

    COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}

    pop_scores = {pop: 0.0 for pop in CONTINENTAL_POPS}
    markers_used = 0
    debug_markers = []

    for marker in aim_markers:
        rsid = marker.get("rsid", "").lower()
        if rsid not in genotypes:
            continue

        allele1, allele2 = genotypes[rsid]
        ref_freqs = marker.get("reference_frequencies", {})
        effect_allele = marker.get("effect_allele", "").upper()
        other_allele = marker.get("other_allele", "").upper()

        if not effect_allele or not ref_freqs:
            continue

        # Strand-aware matching using both alleles when available
        user_alleles = {allele1, allele2}
        effect_count = None

        if other_allele:
            fwd_alleles = {effect_allele, other_allele}
            comp_alleles = {COMPLEMENT.get(effect_allele, effect_allele),
                           COMPLEMENT.get(other_allele, other_allele)}

            if user_alleles <= fwd_alleles:
                # Forward strand match
                effect_count = (1 if allele1 == effect_allele else 0) + (
                    1 if allele2 == effect_allele else 0)
            elif user_alleles <= comp_alleles:
                # Complement strand — count complement of effect allele
                comp_eff = COMPLEMENT.get(effect_allele, effect_allele)
                effect_count = (1 if allele1 == comp_eff else 0) + (
                    1 if allele2 == comp_eff else 0)
            else:
                # User alleles don't match either strand — skip
                continue
        else:
            # Fallback: single-allele matching with complement check
            effect_count = (1 if allele1 == effect_allele else 0) + (
                1 if allele2 == effect_allele else 0)
            comp_allele = COMPLEMENT.get(effect_allele, effect_allele)
            if effect_count == 0 and comp_allele != effect_allele:
                comp_count = (1 if allele1 == comp_allele else 0) + (
                    1 if allele2 == comp_allele else 0)
                if comp_count > 0:
                    effect_count = comp_count

        markers_used += 1
        debug_markers.append({
            "rsid": rsid, "genotype": f"{allele1}/{allele2}",
            "effect_allele": effect_allele, "other_allele": other_allele,
            "effect_count": effect_count, "gene": marker.get("gene", ""),
        })

        for pop in CONTINENTAL_POPS:
            freq = ref_freqs.get(pop, 0.5)
            freq = max(0.001, min(freq, 0.999))

            if effect_count == 2:
                score = 2.0 * _safe_log(freq)
            elif effect_count == 1:
                score = _safe_log(freq) + _safe_log(1 - freq) + _safe_log(2)
            else:
                score = 2.0 * _safe_log(1 - freq)

            pop_scores[pop] += score

    # Write debug log
    _debug_path = os.path.join(os.path.dirname(CURATED_DIR), "ancestry_debug.json")
    try:
        with open(_debug_path, "w") as _f:
            json.dump({"markers_used": markers_used, "markers_total": len(aim_markers),
                        "pop_scores": pop_scores, "marker_details": debug_markers}, _f, indent=2)
    except Exception:
        pass

    if markers_used < 10:
        return _default_composition(
            f"Only {markers_used} ancestry markers found — insufficient for estimation."
        )

    # Convert log-likelihoods to proportions via softmax
    import math
    max_score = max(pop_scores.values())
    exp_scores = {pop: math.exp(score - max_score) for pop, score in pop_scores.items()}
    total = sum(exp_scores.values())

    composition = []
    for pop in CONTINENTAL_POPS:
        pct = (exp_scores[pop] / total) * 100 if total > 0 else 0
        composition.append({
            "population": pop,
            "percentage": round(pct, 1),
        })

    # Sort by percentage descending
    composition.sort(key=lambda x: x["percentage"], reverse=True)

    return composition


def _safe_log(x: float) -> float:
    """Safe log that handles very small values."""
    import math
    return math.log(max(x, 1e-10))


def _default_composition(reason: str) -> list[dict]:
    """Return a placeholder composition when estimation isn't possible."""
    return [{"population": "Unknown", "percentage": 100.0, "note": reason}]
