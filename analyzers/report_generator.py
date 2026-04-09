"""Report generator — orchestrates all analysis modules.

Accepts parsed genotypes and database path, runs all analyzers,
and returns a combined JSON-serializable report.
"""

import time
from typing import Dict, Tuple

from analyzers.health_risks import analyze_health_risks
from analyzers.pharmacogenomics import analyze_pharmacogenomics
from analyzers.traits import analyze_traits
from analyzers.ancestry import analyze_ancestry
from analyzers.polygenic_risk import analyze_polygenic_risk


def generate_report(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> dict:
    """Generate a full DNA analysis report.

    Args:
        genotypes: Dict of rsid → (allele1, allele2) from the parser.
        db_path: Path to the reference SQLite database.

    Returns:
        Complete report dict with all analysis sections.
    """
    start_time = time.time()

    # Run all analysis modules
    health_risks = analyze_health_risks(genotypes, db_path)
    pharma = analyze_pharmacogenomics(genotypes, db_path)
    traits = analyze_traits(genotypes, db_path)
    ancestry = analyze_ancestry(genotypes, db_path)
    polygenic = analyze_polygenic_risk(genotypes, db_path)

    # Build summary statistics
    critical_count = sum(1 for r in health_risks if r["severity"] == "CRITICAL")
    high_count = sum(1 for r in health_risks if r["severity"] == "HIGH")
    drug_interactions = sum(1 for p in pharma if p.get("is_critical"))
    total_drugs = sum(len(p["drugs_affected"]) for p in pharma)

    elapsed = round(time.time() - start_time, 2)

    report = {
        "summary": {
            "total_snps": len(genotypes),
            "analysis_time_seconds": elapsed,
            "critical_count": critical_count,
            "high_count": high_count,
            "health_findings_count": len(health_risks),
            "drug_interactions_count": drug_interactions,
            "total_drugs_analyzed": total_drugs,
            "pharmacogenes_count": len(pharma),
            "traits_count": len(traits),
            "polygenic_conditions_count": len(polygenic),
            "disclaimer": (
                "This report is for educational and informational purposes only. "
                "It is NOT a medical diagnosis. Consult a qualified healthcare "
                "professional or genetic counselor before making any health decisions "
                "based on these results."
            ),
        },
        "health_risks": health_risks,
        "pharmacogenomics": pharma,
        "traits": traits,
        "ancestry": ancestry,
        "polygenic_risk": polygenic,
    }

    return report
