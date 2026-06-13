"""Trait analysis module.

Determines phenotypic traits from genetic variants.
Groups results by category (Nutrition, Physical, Athletic, Sleep, Behavioral).
"""

import json
import logging
import os
import sqlite3
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

from config import CURATED_DIR
from analyzers.alphagenome_scores import get_regulatory
from analyzers.vep_annotations import get_consequence
from analyzers.genotype_match import match_snv, resolve_genotype_key

TRAIT_CATEGORIES = ["Nutrition", "Physical", "Athletic", "Sleep", "Behavioral"]


def analyze_traits(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> list[dict]:
    """Analyze genetic variants for trait predictions.

    Args:
        genotypes: Dict of rsid → (allele1, allele2).
        db_path: Path to the reference SQLite database.

    Returns:
        List of trait finding dicts grouped by category.
    """
    findings = []

    # 1. Curated trait variants (primary source)
    curated_path = os.path.join(CURATED_DIR, "trait_variants.json")
    if os.path.exists(curated_path):
        with open(curated_path) as f:
            trait_variants = json.load(f)
        findings.extend(_analyze_curated_traits(genotypes, trait_variants))

    # 2. Database trait table
    if os.path.exists(db_path):
        findings.extend(_analyze_trait_db(genotypes, db_path))

    # Deduplicate by rsid
    seen = {}
    for f in findings:
        rsid = f["rsid"]
        if rsid not in seen:
            seen[rsid] = f
    findings = list(seen.values())

    # Sort by category then trait name
    category_order = {c: i for i, c in enumerate(TRAIT_CATEGORIES)}
    findings.sort(
        key=lambda x: (category_order.get(x["category"], 99), x["trait"])
    )

    return findings


def _analyze_curated_traits(
    genotypes: Dict[str, Tuple[str, str]],
    trait_variants: list[dict],
) -> list[dict]:
    """Process curated trait variant definitions."""
    findings = []

    for variant in trait_variants:
        rsid = variant.get("rsid", "").lower()
        if rsid not in genotypes:
            continue

        allele1, allele2 = genotypes[rsid]

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

        # The genotype_results values ARE the explanations, so use the result as explanation too
        # Also check for a separate explanations map
        explanation = variant.get("explanations", {}).get(genotype_key, "")
        if not explanation:
            explanation = variant.get("description", "")
        # If the result came from genotype_results, it IS the explanation — use the
        # genotype_results value as explanation and derive a short result label
        if result and result != "Typical" and len(result) > 40:
            explanation = result
            # Keep result as-is (the full description is informative)

        findings.append({
            "rsid": rsid,
            "trait": variant.get("trait", "Unknown trait"),
            "gene": variant.get("gene", ""),
            "category": variant.get("category", "Physical"),
            "your_genotype": f"{allele1}/{allele2}",
            "result": result,
            "explanation": explanation,
            "population_frequency": variant.get("population_frequency", {}),
            "confidence": variant.get("confidence", "moderate"),
            "regulatory": get_regulatory(rsid),
            "consequence": get_consequence(rsid),
        })

    return findings


def _analyze_trait_db(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> list[dict]:
    """Query traits table in the reference database."""
    findings = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='traits'"
        )
        if not cursor.fetchone():
            conn.close()
            return findings

        rsid_list = list(genotypes.keys())
        batch_size = 500

        for i in range(0, len(rsid_list), batch_size):
            batch = rsid_list[i : i + batch_size]
            placeholders = ",".join("?" * len(batch))
            query = f"""
                SELECT rsid, name, gene, category, risk_allele,
                       effect, population_frequency
                FROM traits
                WHERE rsid IN ({placeholders})
            """
            cursor.execute(query, batch)

            for row in cursor.fetchall():
                rsid = row["rsid"]
                allele1, allele2 = genotypes[rsid]
                effect_allele = (row["risk_allele"] or "").upper()

                # Allele-gated traits go through the strand-aware matcher; traits with no
                # risk allele are informational and always surface.
                match_status = None
                if effect_allele:
                    match = match_snv((allele1, allele2), effect_allele)
                    if not match.matched or not match.dosage:
                        continue
                    match_status = match.status

                findings.append({
                    "rsid": rsid,
                    "trait": row["name"] or "Unknown trait",
                    "gene": row["gene"] or "",
                    "category": row["category"] or "Physical",
                    "your_genotype": f"{allele1}/{allele2}",
                    "match_status": match_status,
                    "result": row["effect"] or "Variant detected",
                    "explanation": "",
                    "population_frequency": row["population_frequency"] or 0.0,
                    "confidence": "moderate",
                })

        conn.close()
    except sqlite3.Error as e:
        logger.exception("Trait DB analysis failed: %s", e)

    return findings
