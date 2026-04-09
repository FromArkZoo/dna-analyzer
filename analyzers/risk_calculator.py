"""Utility functions for genetic risk calculations.

Provides odds ratio math, absolute/relative risk calculation,
and helpers for combining multiple risk factors.
"""

import math
from typing import Optional


def calculate_relative_risk(odds_ratio: float) -> float:
    """Convert odds ratio to approximate relative risk.

    For rare diseases (prevalence < 10%), OR ≈ RR.
    For common conditions, applies the Zhang & Yu correction.
    """
    if odds_ratio <= 0:
        return 0.0
    return odds_ratio


def calculate_absolute_risk(
    baseline_rate: float,
    odds_ratio: float,
    zygosity: str = "heterozygous",
) -> dict:
    """Calculate absolute risk from baseline population rate and odds ratio.

    Args:
        baseline_rate: Population baseline risk (0.0 to 1.0).
        odds_ratio: Odds ratio for the risk allele.
        zygosity: 'homozygous' (two risk alleles) or 'heterozygous' (one).

    Returns:
        Dict with absolute_risk, relative_risk, fold_change, and formatted strings.
    """
    if odds_ratio is None:
        odds_ratio = 1.0
    if baseline_rate is None:
        baseline_rate = 0.01
    if baseline_rate <= 0 or baseline_rate >= 1:
        baseline_rate = max(0.001, min(baseline_rate, 0.999))

    effective_or = odds_ratio
    if zygosity == "homozygous":
        # Approximate: homozygous effect ≈ OR^2 under multiplicative model
        effective_or = odds_ratio ** 2

    # Convert OR to probability using baseline
    baseline_odds = baseline_rate / (1 - baseline_rate)
    adjusted_odds = baseline_odds * effective_or
    absolute_risk = adjusted_odds / (1 + adjusted_odds)

    # Clamp
    absolute_risk = max(0.0, min(absolute_risk, 1.0))

    return {
        "absolute_risk": absolute_risk,
        "absolute_risk_pct": f"{absolute_risk * 100:.2f}%",
        "baseline_risk_pct": f"{baseline_rate * 100:.2f}%",
        "relative_risk": calculate_relative_risk(effective_or),
        "fold_change": effective_or,
        "zygosity": zygosity,
    }


def format_risk_percentage(risk: float, precision: int = 2) -> str:
    """Format a risk value (0-1) as a human-readable percentage string."""
    if risk < 0.0001:
        return "<0.01%"
    if risk > 0.9999:
        return ">99.99%"
    return f"{risk * 100:.{precision}f}%"


def confidence_descriptor(stars: int) -> str:
    """Convert review star rating to a confidence label."""
    if stars >= 4:
        return "High confidence"
    if stars >= 2:
        return "Moderate confidence"
    if stars >= 1:
        return "Low confidence"
    return "Very low confidence"


def combine_risk_factors(
    baseline_rate: float,
    risk_factors: list[dict],
) -> dict:
    """Combine multiple independent risk factors using multiplicative model.

    Args:
        baseline_rate: Population baseline risk (0.0 to 1.0).
        risk_factors: List of dicts with 'odds_ratio' and 'zygosity' keys.

    Returns:
        Combined risk estimate dict.
    """
    if not risk_factors:
        return {
            "combined_risk": baseline_rate,
            "combined_risk_pct": format_risk_percentage(baseline_rate),
            "num_factors": 0,
        }

    combined_or = 1.0
    for factor in risk_factors:
        or_val = factor.get("odds_ratio") or 1.0
        zygosity = factor.get("zygosity", "heterozygous")
        if zygosity == "homozygous":
            or_val = or_val ** 2
        combined_or *= or_val

    baseline_odds = baseline_rate / (1 - baseline_rate)
    adjusted_odds = baseline_odds * combined_or
    combined_risk = adjusted_odds / (1 + adjusted_odds)
    combined_risk = max(0.0, min(combined_risk, 1.0))

    return {
        "combined_risk": combined_risk,
        "combined_risk_pct": format_risk_percentage(combined_risk),
        "baseline_risk_pct": format_risk_percentage(baseline_rate),
        "combined_odds_ratio": combined_or,
        "num_factors": len(risk_factors),
    }
