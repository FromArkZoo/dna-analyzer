"""Polygenic Risk Score (PRS) calculation module.

Computes weighted risk scores across multiple SNPs for complex conditions.
"""

import math
import sqlite3
from typing import Dict, Tuple

from scipy.stats import norm


def analyze_polygenic_risk(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> list[dict]:
    """Calculate polygenic risk scores for all available conditions.

    Args:
        genotypes: Dict of rsid → (allele1, allele2).
        db_path: Path to the reference SQLite database.

    Returns:
        List of PRS result dicts per condition.
    """
    results = []

    if not _prs_table_exists(db_path):
        return results

    conditions = _get_prs_conditions(db_path)
    for condition in conditions:
        prs_result = _calculate_prs_for_condition(genotypes, db_path, condition)
        if prs_result:
            results.append(prs_result)

    # Sort by percentile descending (highest risk first)
    results.sort(key=lambda x: x["percentile"], reverse=True)
    return results


def _prs_table_exists(db_path: str) -> bool:
    """Check if the PRS definitions table exists."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prs_weights'"
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    except sqlite3.Error:
        return False


def _get_prs_conditions(db_path: str) -> list[str]:
    """Get list of conditions with PRS definitions."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT condition FROM prs_weights ORDER BY condition")
        conditions = [row[0] for row in cursor.fetchall()]
        conn.close()
        return conditions
    except sqlite3.Error:
        return []


def _calculate_prs_for_condition(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
    condition: str,
) -> dict | None:
    """Calculate PRS for a single condition.

    PRS = Σ(beta_i × effect_allele_count_i)
    Z-score = (PRS - theoretical_mean) / theoretical_SD
    Percentile from normal CDF.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT rsid, effect_allele, beta, effect_allele_freq
            FROM prs_weights
            WHERE condition = ?
            """,
            (condition,),
        )
        snp_weights = cursor.fetchall()
        conn.close()
    except sqlite3.Error:
        return None

    if not snp_weights:
        return None

    total_snps = len(snp_weights)
    raw_score = 0.0
    theoretical_mean = 0.0
    theoretical_var = 0.0
    snps_used = 0

    for snp in snp_weights:
        rsid = snp["rsid"]
        effect_allele = (snp["effect_allele"] or "").upper()
        beta = snp["beta"] or 0.0
        eaf = snp["effect_allele_freq"] or 0.5

        if rsid not in genotypes:
            # For missing SNPs, use expected value (2 * EAF * beta) for mean calculation
            theoretical_mean += 2 * eaf * beta
            theoretical_var += 2 * eaf * (1 - eaf) * (beta ** 2)
            continue

        allele1, allele2 = genotypes[rsid]
        effect_count = (1 if allele1 == effect_allele else 0) + (
            1 if allele2 == effect_allele else 0
        )

        raw_score += beta * effect_count
        snps_used += 1

        # Accumulate theoretical distribution parameters
        theoretical_mean += 2 * eaf * beta
        theoretical_var += 2 * eaf * (1 - eaf) * (beta ** 2)

    # Require >50% SNP coverage
    coverage = snps_used / total_snps if total_snps > 0 else 0
    if coverage < 0.5:
        return None

    # Add expected contribution of missing SNPs to raw score
    for snp in snp_weights:
        rsid = snp["rsid"]
        if rsid not in genotypes:
            eaf = snp["effect_allele_freq"] or 0.5
            beta = snp["beta"] or 0.0
            raw_score += 2 * eaf * beta

    # Calculate Z-score and percentile
    theoretical_sd = math.sqrt(theoretical_var) if theoretical_var > 0 else 1.0
    z_score = (raw_score - theoretical_mean) / theoretical_sd if theoretical_sd > 0 else 0.0
    percentile = norm.cdf(z_score) * 100

    # Interpretation
    interpretation = _interpret_percentile(percentile)

    return {
        "condition": condition,
        "raw_score": round(raw_score, 4),
        "z_score": round(z_score, 2),
        "percentile": round(percentile, 1),
        "coverage_pct": round(coverage * 100, 1),
        "snps_used": snps_used,
        "total_snps": total_snps,
        "interpretation": interpretation,
    }


def _interpret_percentile(percentile: float) -> str:
    """Generate a plain-language interpretation of the PRS percentile."""
    if percentile >= 95:
        return "Very high genetic predisposition — in the top 5% of the population."
    if percentile >= 80:
        return "Above average genetic predisposition — higher than ~80% of the population."
    if percentile >= 60:
        return "Slightly above average genetic predisposition."
    if percentile >= 40:
        return "Average genetic predisposition — near the population median."
    if percentile >= 20:
        return "Slightly below average genetic predisposition."
    if percentile >= 5:
        return "Below average genetic predisposition — lower than ~80% of the population."
    return "Very low genetic predisposition — in the bottom 5% of the population."
