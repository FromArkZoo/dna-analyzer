"""Polygenic Risk Score (PRS) calculation module.

Computes weighted risk scores across multiple SNPs for clinically relevant conditions
using curated PRS definitions with proper effect sizes and allele frequencies.
"""

import logging
import math
import sqlite3
from typing import Dict, Tuple

from scipy.stats import norm

logger = logging.getLogger(__name__)

# Minimum matched SNPs to report a score
MIN_SNPS_USED = 10
# Minimum fraction of the curated panel that must be present
MIN_COVERAGE = 0.5
# Percentile display bounds (consumer PRS shouldn't claim extreme tails)
MIN_PERCENTILE = 2.0
MAX_PERCENTILE = 98.0


def analyze_polygenic_risk(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> list[dict]:
    """Calculate polygenic risk scores for conditions with curated definitions."""
    results = []

    if not _prs_table_exists(db_path):
        return results

    conditions = _get_prs_conditions(db_path)
    for condition in conditions:
        prs_result = _calculate_prs_for_condition(genotypes, db_path, condition)
        if prs_result:
            results.append(prs_result)

    results.sort(key=lambda x: x["percentile"], reverse=True)
    return results


def _prs_table_exists(db_path: str) -> bool:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prs_definitions'"
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    except sqlite3.Error:
        return False


def _get_prs_conditions(db_path: str) -> list[str]:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT trait, COUNT(*) as cnt FROM prs_definitions
            GROUP BY trait HAVING cnt >= 5
            ORDER BY trait
        """)
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
    """Calculate PRS for a single condition using proper per-SNP normalization.

    PRS = sum(beta_i * effect_count_i)
    Theoretical mean = sum(2 * eaf_i * beta_i)
    Theoretical var  = sum(2 * eaf_i * (1-eaf_i) * beta_i^2)
    Z = (PRS - mean) / sqrt(var)
    Percentile = Phi(Z) * 100
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rsid, effect_allele, effect_allele_freq, beta FROM prs_definitions WHERE trait = ?",
            (condition,),
        )
        snp_weights = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        logger.exception("Error querying prs_definitions for %s", condition)
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

        try:
            beta = float(snp["beta"]) if snp["beta"] else 0.0
        except (ValueError, TypeError):
            continue

        # Get per-SNP effect allele frequency
        try:
            eaf = float(snp["effect_allele_freq"]) if snp["effect_allele_freq"] else 0.5
        except (ValueError, TypeError):
            eaf = 0.5
        eaf = max(0.01, min(eaf, 0.99))

        if beta == 0.0 or not effect_allele:
            continue

        # Always accumulate theoretical distribution (for all panel SNPs)
        theoretical_mean += 2 * eaf * beta
        theoretical_var += 2 * eaf * (1 - eaf) * (beta ** 2)

        if rsid not in genotypes:
            # For missing SNPs, add expected value to raw score
            raw_score += 2 * eaf * beta
            continue

        allele1, allele2 = genotypes[rsid]
        effect_count = (1 if allele1 == effect_allele else 0) + (
            1 if allele2 == effect_allele else 0
        )

        raw_score += beta * effect_count
        snps_used += 1

    # Require minimum SNP coverage
    coverage = snps_used / total_snps if total_snps > 0 else 0
    if snps_used < MIN_SNPS_USED or coverage < MIN_COVERAGE:
        return None

    # Calculate Z-score and percentile
    theoretical_sd = math.sqrt(theoretical_var) if theoretical_var > 0 else 1.0
    z_score = (raw_score - theoretical_mean) / theoretical_sd if theoretical_sd > 0 else 0.0

    percentile = norm.cdf(z_score) * 100
    # Clamp to display bounds
    percentile = max(MIN_PERCENTILE, min(MAX_PERCENTILE, percentile))

    return {
        "condition": condition,
        "raw_score": round(raw_score, 4),
        "z_score": round(z_score, 2),
        "percentile": round(percentile, 1),
        "coverage_pct": round(coverage * 100, 1),
        "snps_used": snps_used,
        "total_snps": total_snps,
        "interpretation": _interpret_percentile(percentile),
    }


def _interpret_percentile(percentile: float) -> str:
    if percentile >= 90:
        return "Above average genetic predisposition — higher than ~90% of the population."
    if percentile >= 75:
        return "Moderately above average genetic predisposition."
    if percentile >= 60:
        return "Slightly above average genetic predisposition."
    if percentile >= 40:
        return "Average genetic predisposition — near the population median."
    if percentile >= 25:
        return "Slightly below average genetic predisposition."
    if percentile >= 10:
        return "Moderately below average genetic predisposition."
    return "Below average genetic predisposition — lower than ~90% of the population."
