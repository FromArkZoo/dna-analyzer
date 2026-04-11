"""Health risk analysis from genetic variants.

Queries ClinVar + curated health_variants data against user genotypes.
Classifies findings by severity and zygosity.
"""

import json
import logging
import os
import sqlite3
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

from config import CURATED_DIR, PATHOGENIC_SIGNIFICANCES, SEVERITY_LEVELS
from analyzers.risk_calculator import (
    calculate_absolute_risk,
    confidence_descriptor,
    format_risk_percentage,
)

# APOE allele definitions: rs429358 + rs7412
APOE_SNPS = {
    "rs429358": {"risk_allele": "C", "ref_allele": "T"},
    "rs7412": {"risk_allele": "T", "ref_allele": "C"},
}


def analyze_health_risks(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> list[dict]:
    """Run health risk analysis against ClinVar and curated variants.

    Args:
        genotypes: Dict of rsid → (allele1, allele2).
        db_path: Path to the reference SQLite database.

    Returns:
        List of finding dicts sorted by severity.
    """
    findings = []

    # 1. Query curated health variants
    curated_path = os.path.join(CURATED_DIR, "health_variants.json")
    if os.path.exists(curated_path):
        with open(curated_path) as f:
            curated_variants = json.load(f)
        findings.extend(_analyze_curated_variants(genotypes, curated_variants))

    # 2. Query ClinVar database
    if os.path.exists(db_path):
        findings.extend(_analyze_clinvar(genotypes, db_path))

    # 3. Special APOE analysis
    apoe_result = _analyze_apoe(genotypes)
    if apoe_result:
        findings.append(apoe_result)

    # Deduplicate by rsid (keep highest severity)
    seen = {}
    for f in findings:
        rsid = f["rsid"]
        if rsid not in seen or SEVERITY_LEVELS[f["severity"]]["rank"] < SEVERITY_LEVELS[seen[rsid]["severity"]]["rank"]:
            seen[rsid] = f
    findings = list(seen.values())

    # Sort by severity rank
    findings.sort(key=lambda x: SEVERITY_LEVELS[x["severity"]]["rank"])

    return findings


def _analyze_curated_variants(
    genotypes: Dict[str, Tuple[str, str]],
    curated_variants: list[dict],
) -> list[dict]:
    """Check user genotypes against curated health variant list."""
    findings = []
    for variant in curated_variants:
        rsid = variant.get("rsid", "").lower()
        if rsid not in genotypes:
            continue

        allele1, allele2 = genotypes[rsid]
        risk_allele = variant.get("risk_allele", "").upper()
        if not risk_allele:
            continue

        risk_count = (1 if allele1 == risk_allele else 0) + (
            1 if allele2 == risk_allele else 0
        )
        if risk_count == 0:
            continue

        zygosity = "homozygous" if risk_count == 2 else "heterozygous"
        severity = variant.get("severity", "MODERATE")
        odds_ratio = variant.get("odds_ratio") or 1.0
        baseline_rate = variant.get("population_frequency") or 0.01

        risk_info = calculate_absolute_risk(baseline_rate, odds_ratio, zygosity)

        # Pick the zygosity-specific description if available
        if zygosity == "homozygous":
            specific_desc = variant.get("hom_description", "")
        else:
            specific_desc = variant.get("het_description", "")
        general_desc = variant.get("description", "")

        findings.append({
            "rsid": rsid,
            "gene": variant.get("gene", "Unknown"),
            "condition": variant.get("condition", "Unknown condition"),
            "severity": severity,
            "severity_color": SEVERITY_LEVELS.get(severity, {}).get("color", "#6B7280"),
            "zygosity": zygosity,
            "risk_allele": risk_allele,
            "your_genotype": f"{allele1}/{allele2}",
            "risk_description": general_desc,
            "what_this_means": specific_desc or general_desc,
            "inheritance": variant.get("inheritance", ""),
            "category": variant.get("category", ""),
            "recommendation": variant.get("recommendation", "Consult with a healthcare provider."),
            "confidence_stars": variant.get("confidence_stars", 1),
            "confidence_label": confidence_descriptor(variant.get("confidence_stars", 1)),
            "odds_ratio": odds_ratio,
            "population_frequency": baseline_rate,
            "absolute_risk": risk_info["absolute_risk_pct"],
        })

    return findings


def _analyze_clinvar(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> list[dict]:
    """Query ClinVar table for pathogenic variants matching user genotypes."""
    findings = []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if clinvar table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='clinvar'"
        )
        if not cursor.fetchone():
            conn.close()
            return findings

        # Batch lookup: get all user rsids that appear in clinvar
        rsid_list = list(genotypes.keys())
        batch_size = 500
        for i in range(0, len(rsid_list), batch_size):
            batch = rsid_list[i : i + batch_size]
            placeholders = ",".join("?" * len(batch))
            query = f"""
                SELECT rsid, gene, phenotype, clinical_significance,
                       review_status, alt_allele
                FROM clinvar
                WHERE rsid IN ({placeholders})
                  AND clinical_significance IN ({','.join('?' * len(PATHOGENIC_SIGNIFICANCES))})
            """
            params = batch + PATHOGENIC_SIGNIFICANCES
            cursor.execute(query, params)

            for row in cursor.fetchall():
                rsid = row["rsid"]
                allele1, allele2 = genotypes[rsid]
                risk_allele = (row["alt_allele"] or "").upper()

                if not risk_allele:
                    continue

                risk_count = (1 if allele1 == risk_allele else 0) + (
                    1 if allele2 == risk_allele else 0
                )
                if risk_count == 0:
                    continue

                zygosity = "homozygous" if risk_count == 2 else "heterozygous"
                stars = _review_status_to_stars(row["review_status"])
                odds_ratio = 1.0

                severity = _classify_severity(
                    row["clinical_significance"], stars, odds_ratio, zygosity
                )

                findings.append({
                    "rsid": rsid,
                    "gene": row["gene"] or "Unknown",
                    "condition": row["phenotype"] or "Unknown condition",
                    "severity": severity,
                    "severity_color": SEVERITY_LEVELS.get(severity, {}).get("color", "#6B7280"),
                    "zygosity": zygosity,
                    "risk_allele": risk_allele,
                    "your_genotype": f"{allele1}/{allele2}",
                    "risk_description": f"{row['clinical_significance']} variant in {row['gene'] or 'unknown gene'}",
                    "recommendation": "Discuss this finding with a genetic counselor.",
                    "confidence_stars": stars,
                    "confidence_label": confidence_descriptor(stars),
                    "odds_ratio": odds_ratio,
                    "population_frequency": 0.0,
                    "absolute_risk": "N/A",
                })

        conn.close()
    except sqlite3.Error as e:
        logger.exception("ClinVar analysis failed: %s", e)

    return findings


def _review_status_to_stars(review_status: str) -> int:
    """Map ClinVar review_status text to a star rating (0-4)."""
    if not review_status:
        return 0
    status = review_status.lower()
    if "practice guideline" in status:
        return 4
    if "reviewed by expert panel" in status:
        return 3
    if "multiple submitters" in status:
        return 2
    if "single submitter" in status or "criteria provided" in status:
        return 1
    return 0


def _classify_severity(
    significance: str, stars: int, odds_ratio: float, zygosity: str
) -> str:
    """Classify a variant's severity based on multiple factors."""
    if "athogenic" in significance:  # Pathogenic or Likely pathogenic
        if zygosity == "homozygous" and (odds_ratio > 5 or stars >= 3):
            return "CRITICAL"
        if odds_ratio > 3 or stars >= 3:
            return "HIGH"
        return "MODERATE"
    return "LOW"


def _analyze_apoe(genotypes: Dict[str, Tuple[str, str]]) -> dict | None:
    """Determine APOE genotype from rs429358 + rs7412 combination."""
    rs429358 = genotypes.get("rs429358")
    rs7412 = genotypes.get("rs7412")

    if not rs429358 or not rs7412:
        return None

    # Determine APOE isoforms
    # ε2: rs429358=T/T, rs7412=T/T  → APOE ε2/ε2
    # ε3: rs429358=T/T, rs7412=C/C  → APOE ε3/ε3 (reference)
    # ε4: rs429358=C/C, rs7412=C/C  → APOE ε4/ε4
    # Mixed combinations give ε2/ε3, ε2/ε4, ε3/ε4

    def _apoe_haplotype(rs429358_allele: str, rs7412_allele: str) -> str:
        if rs429358_allele == "T" and rs7412_allele == "T":
            return "ε2"
        elif rs429358_allele == "T" and rs7412_allele == "C":
            return "ε3"
        elif rs429358_allele == "C" and rs7412_allele == "C":
            return "ε4"
        else:
            return "ε?"  # rare C/T at both — shouldn't normally occur

    hap1 = _apoe_haplotype(rs429358[0], rs7412[0])
    hap2 = _apoe_haplotype(rs429358[1], rs7412[1])

    apoe_type = "/".join(sorted([hap1, hap2]))

    # Risk assessment
    severity = "LOW"
    risk_desc = ""
    recommendation = "No specific action needed for Alzheimer's risk based on APOE genotype."

    if "ε4" in apoe_type:
        if apoe_type == "ε4/ε4":
            severity = "HIGH"
            risk_desc = (
                "APOE ε4/ε4 homozygous — significantly elevated risk for "
                "late-onset Alzheimer's disease (8-12x increased risk vs ε3/ε3). "
                "Also associated with increased cardiovascular risk."
            )
            recommendation = (
                "Discuss with a genetic counselor. Consider proactive cognitive "
                "health strategies, cardiovascular risk management, and regular "
                "health monitoring."
            )
        else:
            severity = "MODERATE"
            risk_desc = (
                f"APOE {apoe_type} — moderately elevated risk for late-onset "
                "Alzheimer's disease (2-3x increased risk vs ε3/ε3)."
            )
            recommendation = (
                "Maintain cardiovascular health and cognitive engagement. "
                "Consider discussing with a healthcare provider."
            )
    elif "ε2" in apoe_type:
        severity = "PROTECTIVE"
        risk_desc = (
            f"APOE {apoe_type} — the ε2 allele is associated with reduced "
            "risk for late-onset Alzheimer's disease."
        )
        recommendation = "This is generally considered a favorable finding."
    else:
        risk_desc = f"APOE {apoe_type} — reference genotype with average population risk."

    return {
        "rsid": "APOE (rs429358+rs7412)",
        "gene": "APOE",
        "condition": "Alzheimer's disease risk / Cardiovascular risk",
        "severity": severity,
        "severity_color": SEVERITY_LEVELS.get(severity, {}).get("color", "#6B7280"),
        "zygosity": apoe_type,
        "risk_allele": "ε4",
        "your_genotype": apoe_type,
        "risk_description": risk_desc,
        "recommendation": recommendation,
        "confidence_stars": 4,
        "confidence_label": "High confidence",
        "odds_ratio": 12.0 if apoe_type == "ε4/ε4" else (3.0 if "ε4" in apoe_type else 0.6 if "ε2" in apoe_type else 1.0),
        "population_frequency": 0.14,
        "absolute_risk": "N/A",
    }
