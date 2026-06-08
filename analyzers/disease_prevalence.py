"""Resolve a finding's condition to a population disease-prevalence baseline.

The absolute-risk calculation needs the population DISEASE rate as its baseline
(e.g. ~12.5% lifetime for breast cancer), not the variant's allele frequency.
This maps a free-text `condition` to an entry in `disease_prevalence.json`,
returning (canonical_name, general_population_rate) or (None, None) when there is
no disease baseline — e.g. trait or drug-response findings, which should then
report absolute risk as N/A rather than a fabricated number.
"""
import json
import os

from config import CURATED_DIR

_DP = None

# Conditions whose wording doesn't contain the disease_prevalence key verbatim.
_ALIASES = {
    "hereditary breast and ovarian cancer syndrome": "Breast Cancer",
    "myocardial infarction": "Coronary Artery Disease",
}


def _load() -> dict:
    global _DP
    if _DP is None:
        try:
            with open(os.path.join(CURATED_DIR, "disease_prevalence.json")) as f:
                raw = json.load(f)
            _DP = {}
            for name, v in raw.items():
                rate = v.get("general_population_rate") if isinstance(v, dict) else v
                if isinstance(rate, (int, float)) and 0 < rate < 1:
                    _DP[name] = rate
        except (FileNotFoundError, json.JSONDecodeError):
            _DP = {}
    return _DP


def disease_baseline(condition):
    """Return (canonical_disease_name, population_rate) for a condition, or (None, None)."""
    dp = _load()
    if not condition or not dp:
        return None, None
    c = condition.lower()
    for alias, target in _ALIASES.items():
        if alias in c and target in dp:
            return target, dp[target]
    # Prefer the most specific (longest) disease name that appears in the condition.
    for name in sorted(dp, key=len, reverse=True):
        if name.lower() in c:
            return name, dp[name]
    return None, None
