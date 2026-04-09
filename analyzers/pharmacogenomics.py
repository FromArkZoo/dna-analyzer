"""Pharmacogenomics analysis module.

Determines metabolizer status for pharmacogenes and maps to drug guidance.
Flags critical drug-gene interactions.
"""

import json
import os
import sqlite3
from typing import Dict, Tuple

from config import CURATED_DIR

# Critical drug-gene interactions that require immediate clinical attention
CRITICAL_INTERACTIONS = {
    "DPYD": {
        "drugs": ["fluorouracil", "capecitabine", "tegafur"],
        "warning": "CRITICAL: Variants in DPYD can cause life-threatening toxicity with fluoropyrimidine chemotherapy (5-FU, capecitabine). Pre-treatment DPYD testing is strongly recommended.",
    },
    "HLA-B": {
        "alleles": ["*57:01"],
        "drugs": ["abacavir"],
        "warning": "CRITICAL: HLA-B*57:01 carriers must NOT receive abacavir — high risk of severe hypersensitivity reaction.",
    },
    "HLA-A": {
        "alleles": ["*31:01"],
        "drugs": ["carbamazepine"],
        "warning": "CRITICAL: HLA-A*31:01 increases risk of severe cutaneous adverse reactions with carbamazepine.",
    },
}

# Metabolizer status definitions
METABOLIZER_STATUS = {
    "PM": "Poor Metabolizer",
    "IM": "Intermediate Metabolizer",
    "NM": "Normal Metabolizer",
    "RM": "Rapid Metabolizer",
    "UM": "Ultra-rapid Metabolizer",
}


def analyze_pharmacogenomics(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> list[dict]:
    """Analyze pharmacogenomic variants for drug response prediction.

    Args:
        genotypes: Dict of rsid → (allele1, allele2).
        db_path: Path to the reference SQLite database.

    Returns:
        List of pharmacogene result dicts.
    """
    results = []

    # 1. Load curated pharma variants
    curated_path = os.path.join(CURATED_DIR, "pharma_variants.json")
    if os.path.exists(curated_path):
        with open(curated_path) as f:
            pharma_data = json.load(f)
        results.extend(_analyze_curated_pharma(genotypes, pharma_data))

    # 2. Query PharmGKB database tables
    if os.path.exists(db_path):
        results.extend(_analyze_pharmgkb_db(genotypes, db_path))

    # Deduplicate by gene (keep curated over DB)
    seen_genes = {}
    for r in results:
        gene = r["gene"]
        if gene not in seen_genes:
            seen_genes[gene] = r
    results = list(seen_genes.values())

    # Flag critical interactions
    for result in results:
        _flag_critical_interactions(result)

    # Sort: critical first, then alphabetical by gene
    results.sort(key=lambda x: (0 if x.get("is_critical") else 1, x["gene"]))

    return results


def _analyze_curated_pharma(
    genotypes: Dict[str, Tuple[str, str]],
    pharma_data: list[dict],
) -> list[dict]:
    """Process curated pharmacogenomic variant definitions."""
    gene_results = {}

    for entry in pharma_data:
        rsid = entry.get("rsid", "").lower()
        if rsid not in genotypes:
            continue

        allele1, allele2 = genotypes[rsid]
        gene = entry.get("gene", "Unknown")

        if gene not in gene_results:
            gene_results[gene] = {
                "gene": gene,
                "tested_variants": [],
                "star_alleles": "*1/*1",  # default reference
                "metabolizer_status": "Normal Metabolizer",
                "metabolizer_code": "NM",
                "drugs_affected": [],
                "is_critical": False,
                "critical_warning": None,
            }

        variant_allele = entry.get("variant_allele", "").upper()
        star_allele = entry.get("star_allele", "")
        variant_count = (1 if allele1 == variant_allele else 0) + (
            1 if allele2 == variant_allele else 0
        )

        gene_results[gene]["tested_variants"].append({
            "rsid": rsid,
            "genotype": f"{allele1}/{allele2}",
            "variant_allele": variant_allele,
            "variant_count": variant_count,
        })

        if variant_count > 0 and star_allele:
            _update_star_alleles(gene_results[gene], star_allele, variant_count)

        # Determine metabolizer status from entry's phenotype map
        if variant_count > 0:
            phenotype_map = entry.get("phenotype_map", {})
            status_key = "homozygous" if variant_count == 2 else "heterozygous"
            if status_key in phenotype_map:
                status = phenotype_map[status_key]
                gene_results[gene]["metabolizer_status"] = METABOLIZER_STATUS.get(
                    status, status
                )
                gene_results[gene]["metabolizer_code"] = status

            # Add affected drugs
            for drug_info in entry.get("drugs", []):
                drug_entry = {
                    "drug": drug_info.get("name", "Unknown"),
                    "guidance": drug_info.get(
                        "guidance", {}).get(
                        status_key, drug_info.get("guidance", {}).get("default", "Standard dosing.")),
                    "category": drug_info.get("category", ""),
                    "source": drug_info.get("source", "PharmGKB"),
                }
                # Avoid duplicate drugs
                existing_drugs = {d["drug"] for d in gene_results[gene]["drugs_affected"]}
                if drug_entry["drug"] not in existing_drugs:
                    gene_results[gene]["drugs_affected"].append(drug_entry)

    return list(gene_results.values())


def _analyze_pharmgkb_db(
    genotypes: Dict[str, Tuple[str, str]],
    db_path: str,
) -> list[dict]:
    """Query PharmGKB tables in the reference database."""
    results = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pharmgkb'"
        )
        if not cursor.fetchone():
            conn.close()
            return results

        rsid_list = list(genotypes.keys())
        batch_size = 500
        gene_data = {}

        for i in range(0, len(rsid_list), batch_size):
            batch = rsid_list[i : i + batch_size]
            placeholders = ",".join("?" * len(batch))
            query = f"""
                SELECT rsid, gene, variant_allele, star_allele,
                       metabolizer_status, drug_name, drug_guidance
                FROM pharmgkb
                WHERE rsid IN ({placeholders})
            """
            cursor.execute(query, batch)

            for row in cursor.fetchall():
                rsid = row["rsid"]
                gene = row["gene"] or "Unknown"
                allele1, allele2 = genotypes[rsid]
                variant_allele = (row["variant_allele"] or "").upper()

                variant_count = (1 if allele1 == variant_allele else 0) + (
                    1 if allele2 == variant_allele else 0
                )
                if variant_count == 0:
                    continue

                if gene not in gene_data:
                    gene_data[gene] = {
                        "gene": gene,
                        "tested_variants": [],
                        "star_alleles": row["star_allele"] or "*1/*1",
                        "metabolizer_status": row["metabolizer_status"] or "Normal Metabolizer",
                        "metabolizer_code": "NM",
                        "drugs_affected": [],
                        "is_critical": False,
                        "critical_warning": None,
                    }

                if row["drug_name"]:
                    existing_drugs = {d["drug"] for d in gene_data[gene]["drugs_affected"]}
                    if row["drug_name"] not in existing_drugs:
                        gene_data[gene]["drugs_affected"].append({
                            "drug": row["drug_name"],
                            "guidance": row["drug_guidance"] or "See PharmGKB for guidance.",
                            "category": "",
                            "source": "PharmGKB DB",
                        })

        results = list(gene_data.values())
        conn.close()
    except sqlite3.Error:
        pass

    return results


def _update_star_alleles(gene_result: dict, star_allele: str, count: int):
    """Update the star allele call for a gene based on variant findings."""
    if count == 2:
        gene_result["star_alleles"] = f"{star_allele}/{star_allele}"
    elif count == 1:
        gene_result["star_alleles"] = f"*1/{star_allele}"


def _flag_critical_interactions(result: dict):
    """Check if a gene result involves a critical drug-gene interaction."""
    gene = result["gene"]
    if gene in CRITICAL_INTERACTIONS:
        critical = CRITICAL_INTERACTIONS[gene]
        result["is_critical"] = True
        result["critical_warning"] = critical["warning"]
        # Mark specific drugs as critical
        critical_drugs = {d.lower() for d in critical.get("drugs", [])}
        for drug in result["drugs_affected"]:
            if drug["drug"].lower() in critical_drugs:
                drug["is_critical"] = True
