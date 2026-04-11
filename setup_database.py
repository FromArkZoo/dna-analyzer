#!/usr/bin/env python3
"""
Download public genomic databases and build a local SQLite reference DB.

Sources:
  - ClinVar variant_summary.txt.gz  (NCBI)
  - GWAS Catalog full download       (EBI)
  - PharmGKB clinical annotations     (PharmGKB)
  - Curated JSON files in data/curated/

Usage:
  python setup_database.py            # download + build everything
  python setup_database.py --skip-download   # rebuild DB from cached files
"""

import argparse
import gzip
import io
import json
import math
import os
import sqlite3
import sys
import zipfile
from datetime import datetime

import pandas as pd
import requests

from config import (
    ASSEMBLY,
    CLINVAR_URL,
    CURATED_DIR,
    DB_PATH,
    DOWNLOADS_DIR,
    GWAS_CATALOG_URL,
    GWAS_P_VALUE_THRESHOLD,
    PHARMGKB_URL,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def progress(msg):
    """Print a timestamped progress message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def download_file(url, dest_path, description="file"):
    """Download a URL to a local path with progress reporting."""
    if os.path.exists(dest_path):
        progress(f"  {description} already cached at {dest_path}")
        return
    progress(f"  Downloading {description} ...")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                print(f"\r  {description}: {pct}% ({downloaded // 1024 // 1024} MB)", end="", flush=True)
    print()
    progress(f"  {description} saved ({downloaded // 1024 // 1024} MB)")


def load_json(filename):
    """Load a JSON file from the curated directory."""
    path = os.path.join(CURATED_DIR, filename)
    if not os.path.exists(path):
        progress(f"  WARNING: curated file {filename} not found — skipping")
        return None
    with open(path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Download sources
# ---------------------------------------------------------------------------

def download_all():
    """Download all external data sources."""
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    # ClinVar
    clinvar_path = os.path.join(DOWNLOADS_DIR, "variant_summary.txt.gz")
    download_file(CLINVAR_URL, clinvar_path, "ClinVar variant_summary")

    # GWAS Catalog (now distributed as ZIP)
    gwas_zip_path = os.path.join(DOWNLOADS_DIR, "gwas_catalog_full.zip")
    gwas_tsv_path = os.path.join(DOWNLOADS_DIR, "gwas_catalog_full.tsv")
    download_file(GWAS_CATALOG_URL, gwas_zip_path, "GWAS Catalog")
    if os.path.exists(gwas_zip_path) and not os.path.exists(gwas_tsv_path):
        import zipfile as _zf
        progress("  Extracting GWAS Catalog ZIP ...")
        with _zf.ZipFile(gwas_zip_path, "r") as zf:
            # Find the TSV file inside the ZIP
            tsv_names = [n for n in zf.namelist() if n.endswith(".tsv")]
            if tsv_names:
                with zf.open(tsv_names[0]) as src, open(gwas_tsv_path, "wb") as dst:
                    dst.write(src.read())
                progress(f"  Extracted {tsv_names[0]}")
            else:
                # Fall back to first file
                first = zf.namelist()[0]
                with zf.open(first) as src, open(gwas_tsv_path, "wb") as dst:
                    dst.write(src.read())
                progress(f"  Extracted {first}")

    # PharmGKB
    pharmgkb_path = os.path.join(DOWNLOADS_DIR, "clinicalAnnotations.zip")
    download_file(PHARMGKB_URL, pharmgkb_path, "PharmGKB clinical annotations")


# ---------------------------------------------------------------------------
# ClinVar processing
# ---------------------------------------------------------------------------

def process_clinvar(conn):
    """Parse, filter, and load ClinVar data into SQLite using chunked reading."""
    progress("Processing ClinVar ...")
    gz_path = os.path.join(DOWNLOADS_DIR, "variant_summary.txt.gz")
    if not os.path.exists(gz_path):
        progress("  ERROR: ClinVar file not found — run without --skip-download first")
        return

    # Only read the columns we need — much faster than loading all ~40 columns
    use_cols = [
        "Type", "Assembly", "RS# (dbSNP)", "OriginSimple",
        "ClinicalSignificance", "PhenotypeList", "GeneSymbol",
        "Chromosome", "PositionVCF", "ReferenceAlleleVCF",
        "AlternateAlleleVCF", "ReviewStatus",
    ]

    col_rename = {
        "RS# (dbSNP)": "rs_number",
        "ClinicalSignificance": "clinical_significance",
        "PhenotypeList": "phenotype",
        "GeneSymbol": "gene",
        "Chromosome": "chromosome",
        "PositionVCF": "position",
        "ReferenceAlleleVCF": "ref_allele",
        "AlternateAlleleVCF": "alt_allele",
        "ReviewStatus": "review_status",
    }

    keep_cols = [
        "rsid", "gene", "clinical_significance", "phenotype",
        "chromosome", "position", "ref_allele", "alt_allele", "review_status",
    ]

    total_raw = 0
    total_loaded = 0
    first_chunk = True
    chunk_size = 200_000

    progress("  Reading ClinVar in chunks ...")
    with gzip.open(gz_path, "rt") as f:
        for chunk in pd.read_csv(f, sep="\t", dtype=str, usecols=use_cols, chunksize=chunk_size):
            total_raw += len(chunk)

            # Filter
            chunk = chunk[chunk["Type"] == "single nucleotide variant"]
            chunk = chunk[chunk["Assembly"] == ASSEMBLY]
            chunk = chunk[chunk["RS# (dbSNP)"] != "-1"]
            chunk = chunk[chunk["RS# (dbSNP)"].notna()]
            if "OriginSimple" in chunk.columns:
                chunk = chunk[chunk["OriginSimple"].str.lower().str.contains("germline", na=False)]

            if chunk.empty:
                continue

            chunk = chunk.rename(columns=col_rename)
            chunk["rsid"] = "rs" + chunk["rs_number"].astype(str)
            chunk = chunk[[c for c in keep_cols if c in chunk.columns]]
            chunk = chunk.drop_duplicates(subset=["rsid", "clinical_significance", "phenotype"])

            mode = "replace" if first_chunk else "append"
            chunk.to_sql("clinvar", conn, if_exists=mode, index=False)
            total_loaded += len(chunk)
            first_chunk = False
            print(f"\r  Processed {total_raw:,} rows, kept {total_loaded:,} ...", end="", flush=True)

    print()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clinvar_rsid ON clinvar(rsid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clinvar_gene ON clinvar(gene)")
    progress(f"  ClinVar: {total_raw:,} raw → {total_loaded:,} loaded")


# ---------------------------------------------------------------------------
# GWAS Catalog processing
# ---------------------------------------------------------------------------

def process_gwas(conn):
    """Parse, filter, and load GWAS Catalog data into SQLite."""
    progress("Processing GWAS Catalog ...")
    tsv_path = os.path.join(DOWNLOADS_DIR, "gwas_catalog_full.tsv")
    if not os.path.exists(tsv_path):
        progress("  ERROR: GWAS file not found — run without --skip-download first")
        return

    df = pd.read_csv(tsv_path, sep="\t", dtype=str, low_memory=False)
    progress(f"  Raw GWAS rows: {len(df):,}")

    # Identify column names (GWAS catalog uses various formats)
    pval_col = None
    for candidate in ["P-VALUE", "P_VALUE", "PVALUE_MLOG"]:
        if candidate in df.columns:
            pval_col = candidate
            break

    snp_col = None
    for candidate in ["SNPS", "SNP_ID_CURRENT"]:
        if candidate in df.columns:
            snp_col = candidate
            break

    or_col = None
    for candidate in ["OR or BETA", "OR_or_BETA", "OR"]:
        if candidate in df.columns:
            or_col = candidate
            break

    if not pval_col or not snp_col:
        progress("  ERROR: Could not identify required GWAS columns")
        progress(f"  Available columns: {list(df.columns)}")
        return

    # Filter for valid rsIDs
    df = df[df[snp_col].str.startswith("rs", na=False)]

    # Filter by p-value
    if pval_col == "PVALUE_MLOG":
        # -log10(p) format: 5e-8 => -log10 ≈ 7.3
        df[pval_col] = pd.to_numeric(df[pval_col], errors="coerce")
        mlog_threshold = -math.log10(GWAS_P_VALUE_THRESHOLD)
        df = df[df[pval_col] >= mlog_threshold]
    else:
        df[pval_col] = pd.to_numeric(df[pval_col], errors="coerce")
        df = df[df[pval_col] < GWAS_P_VALUE_THRESHOLD]

    # Filter: must have OR or BETA value
    if or_col:
        df[or_col] = pd.to_numeric(df[or_col], errors="coerce")
        df = df[df[or_col].notna()]

    progress(f"  After filtering: {len(df):,} associations")

    # Map to clean column names
    trait_col = None
    for candidate in ["DISEASE/TRAIT", "DISEASE_TRAIT", "MAPPED_TRAIT"]:
        if candidate in df.columns:
            trait_col = candidate
            break

    risk_allele_col = None
    for candidate in ["STRONGEST SNP-RISK ALLELE", "STRONGEST_SNP_RISK_ALLELE"]:
        if candidate in df.columns:
            risk_allele_col = candidate
            break

    ci_col = None
    for candidate in ["95% CI (TEXT)", "95_CI_TEXT"]:
        if candidate in df.columns:
            ci_col = candidate
            break

    gene_col = None
    for candidate in ["REPORTED GENE(S)", "REPORTED_GENES", "MAPPED_GENE"]:
        if candidate in df.columns:
            gene_col = candidate
            break

    records = pd.DataFrame()
    records["rsid"] = df[snp_col]
    records["trait"] = df[trait_col] if trait_col else ""
    records["p_value"] = df[pval_col]
    records["or_beta"] = df[or_col] if or_col else None
    records["risk_allele"] = df[risk_allele_col] if risk_allele_col else ""
    records["ci_95"] = df[ci_col] if ci_col else ""
    records["gene"] = df[gene_col] if gene_col else ""
    records["pubmed_id"] = df["PUBMEDID"] if "PUBMEDID" in df.columns else ""

    records = records.drop_duplicates(subset=["rsid", "trait"])

    records.to_sql("gwas", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gwas_rsid ON gwas(rsid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gwas_trait ON gwas(trait)")
    progress(f"  Loaded {len(records):,} GWAS records")


# ---------------------------------------------------------------------------
# PharmGKB processing
# ---------------------------------------------------------------------------

def process_pharmgkb(conn):
    """Parse and load PharmGKB clinical annotation data."""
    progress("Processing PharmGKB ...")
    zip_path = os.path.join(DOWNLOADS_DIR, "clinicalAnnotations.zip")
    if not os.path.exists(zip_path):
        progress("  ERROR: PharmGKB file not found — run without --skip-download first")
        return

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Find the main annotations file
        annotation_file = None
        alleles_file = None
        for name in zf.namelist():
            if "clinical_annotations" in name.lower() and name.endswith(".tsv"):
                annotation_file = name
            if "clinical_ann_alleles" in name.lower() and name.endswith(".tsv"):
                alleles_file = name

        if not annotation_file:
            # Try alternative naming
            for name in zf.namelist():
                if name.endswith(".tsv"):
                    progress(f"  Found: {name}")
            progress("  ERROR: Could not find annotations TSV in PharmGKB zip")
            return

        # Load main annotations
        progress(f"  Reading {annotation_file}")
        with zf.open(annotation_file) as f:
            df = pd.read_csv(io.TextIOWrapper(f), sep="\t", dtype=str)

        progress(f"  Raw PharmGKB annotation rows: {len(df):,}")

        # Build rsid column from Variant/Haplotypes or Location
        rsid_col = None
        for candidate in ["Variant/Haplotypes", "Variant", "variantId"]:
            if candidate in df.columns:
                rsid_col = candidate
                break

        if rsid_col:
            df = df[df[rsid_col].str.startswith("rs", na=False)]
            df = df.rename(columns={rsid_col: "rsid"})

        gene_col = None
        for candidate in ["Gene", "gene"]:
            if candidate in df.columns:
                gene_col = candidate
                break

        drug_col = None
        for candidate in ["Drug(s)", "Chemical", "Chemicals", "relatedChemicals"]:
            if candidate in df.columns:
                drug_col = candidate
                break

        phenotype_col = None
        for candidate in ["Phenotype(s)", "Phenotype Category", "phenotypeCategory"]:
            if candidate in df.columns:
                phenotype_col = candidate
                break

        level_col = None
        for candidate in ["Level of Evidence", "evidenceLevel", "Evidence Level"]:
            if candidate in df.columns:
                level_col = candidate
                break

        ann_id_col = None
        for candidate in ["Clinical Annotation ID", "clinicalAnnotationId"]:
            if candidate in df.columns:
                ann_id_col = candidate
                break

        records = pd.DataFrame()
        records["rsid"] = df["rsid"]
        if ann_id_col:
            records["annotation_id"] = df[ann_id_col]
        records["gene"] = df[gene_col] if gene_col else ""
        records["drug"] = df[drug_col] if drug_col else ""
        records["phenotype_category"] = df[phenotype_col] if phenotype_col else ""
        records["evidence_level"] = df[level_col] if level_col else ""

        records.to_sql("pharmgkb", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pharmgkb_rsid ON pharmgkb(rsid)")
        progress(f"  Loaded {len(records):,} PharmGKB annotations")

        # Load alleles table if available
        if alleles_file:
            progress(f"  Reading {alleles_file}")
            with zf.open(alleles_file) as f:
                adf = pd.read_csv(io.TextIOWrapper(f), sep="\t", dtype=str)

            progress(f"  Raw allele rows: {len(adf):,}")

            allele_ann_id_col = None
            for candidate in ["Clinical Annotation ID", "clinicalAnnotationId"]:
                if candidate in adf.columns:
                    allele_ann_id_col = candidate
                    break

            allele_genotype_col = None
            for candidate in ["Genotype/Allele", "Allele", "genotype"]:
                if candidate in adf.columns:
                    allele_genotype_col = candidate
                    break

            allele_annotation_col = None
            for candidate in ["Annotation Text", "annotationText", "Sentence"]:
                if candidate in adf.columns:
                    allele_annotation_col = candidate
                    break

            fn_col = None
            for candidate in ["Allele Function", "alleleFunctionImpact"]:
                if candidate in adf.columns:
                    fn_col = candidate
                    break

            allele_records = pd.DataFrame()
            if allele_ann_id_col:
                allele_records["annotation_id"] = adf[allele_ann_id_col]
            if allele_genotype_col:
                allele_records["genotype"] = adf[allele_genotype_col]
            if allele_annotation_col:
                allele_records["annotation_text"] = adf[allele_annotation_col]
            if fn_col:
                allele_records["allele_function"] = adf[fn_col]

            allele_records.to_sql("pharmgkb_alleles", conn, if_exists="replace", index=False)
            if "annotation_id" in allele_records.columns:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pgkb_alleles_annid ON pharmgkb_alleles(annotation_id)")
            progress(f"  Loaded {len(allele_records):,} PharmGKB allele records")
        else:
            # Create empty table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pharmgkb_alleles (
                    annotation_id TEXT, genotype TEXT,
                    annotation_text TEXT, allele_function TEXT
                )
            """)
            progress("  No alleles file found — created empty pharmgkb_alleles table")


# ---------------------------------------------------------------------------
# Curated data loading
# ---------------------------------------------------------------------------

def load_curated_traits(conn):
    """Load curated health variants and trait variants into a unified traits table."""
    progress("Loading curated trait/health data ...")

    all_rows = []

    # Health variants
    health = load_json("health_variants.json")
    if health:
        for entry in health:
            rsid = entry.get("rsid", "")
            all_rows.append({
                "rsid": rsid,
                "category": "health",
                "name": entry.get("name", entry.get("trait", "")),
                "gene": entry.get("gene", ""),
                "risk_allele": entry.get("risk_allele", ""),
                "effect": entry.get("effect", entry.get("description", "")),
                "severity": entry.get("severity", "MODERATE"),
                "odds_ratio": str(entry.get("odds_ratio", "")),
                "population_frequency": str(entry.get("frequency", entry.get("population_frequency", ""))),
            })
        progress(f"  health_variants.json: {len(health)} entries")

    # Trait variants
    traits = load_json("trait_variants.json")
    if traits:
        for entry in traits:
            rsid = entry.get("rsid", "")
            all_rows.append({
                "rsid": rsid,
                "category": entry.get("category", "trait"),
                "name": entry.get("name", entry.get("trait", "")),
                "gene": entry.get("gene", ""),
                "risk_allele": entry.get("effect_allele", entry.get("risk_allele", "")),
                "effect": entry.get("effect", entry.get("description", "")),
                "severity": entry.get("severity", ""),
                "odds_ratio": str(entry.get("odds_ratio", "")),
                "population_frequency": str(entry.get("frequency", entry.get("population_frequency", ""))),
            })
        progress(f"  trait_variants.json: {len(traits)} entries")

    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_sql("traits", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traits_rsid ON traits(rsid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traits_category ON traits(category)")
        progress(f"  Total traits loaded: {len(df)}")
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traits (
                rsid TEXT, category TEXT, name TEXT, gene TEXT,
                risk_allele TEXT, effect TEXT, severity TEXT,
                odds_ratio TEXT, population_frequency TEXT
            )
        """)
        progress("  No trait data found — created empty traits table")


def load_curated_haplogroups(conn):
    """Load haplogroup tree data into mtdna_haplogroups and ydna_haplogroups tables."""
    progress("Loading curated haplogroup data ...")

    data = load_json("haplogroup_tree.json")
    if not data:
        # Create empty tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mtdna_haplogroups (
                haplogroup TEXT, rsid TEXT, position TEXT,
                ancestral TEXT, derived TEXT, region TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ydna_haplogroups (
                haplogroup TEXT, rsid TEXT, position TEXT,
                ancestral TEXT, derived TEXT, region TEXT
            )
        """)
        progress("  No haplogroup data found — created empty tables")
        return

    # Process mtDNA haplogroups
    mt_rows = []
    mt_data = data.get("mtdna", data.get("mtDNA", []))
    if isinstance(mt_data, dict):
        mt_data = list(mt_data.values()) if not isinstance(list(mt_data.values())[0], str) else [mt_data]
    for entry in mt_data:
        if isinstance(entry, dict):
            snps = entry.get("defining_snps", entry.get("snps", []))
            if isinstance(snps, list):
                for snp in snps:
                    if isinstance(snp, dict):
                        mt_rows.append({
                            "haplogroup": entry.get("haplogroup", entry.get("name", "")),
                            "rsid": snp.get("rsid", ""),
                            "position": str(snp.get("position", "")),
                            "ancestral": snp.get("ancestral", snp.get("ref", "")),
                            "derived": snp.get("derived", snp.get("alt", "")),
                            "region": entry.get("region", entry.get("origin", "")),
                        })
                    elif isinstance(snp, str):
                        mt_rows.append({
                            "haplogroup": entry.get("haplogroup", entry.get("name", "")),
                            "rsid": snp if snp.startswith("rs") else "",
                            "position": snp if not snp.startswith("rs") else "",
                            "ancestral": "",
                            "derived": "",
                            "region": entry.get("region", entry.get("origin", "")),
                        })
            # Handle case where rsid is directly on the entry
            elif "rsid" in entry:
                mt_rows.append({
                    "haplogroup": entry.get("haplogroup", entry.get("name", "")),
                    "rsid": entry["rsid"],
                    "position": str(entry.get("position", "")),
                    "ancestral": entry.get("ancestral", entry.get("ref", "")),
                    "derived": entry.get("derived", entry.get("alt", "")),
                    "region": entry.get("region", entry.get("origin", "")),
                })

    if mt_rows:
        pd.DataFrame(mt_rows).to_sql("mtdna_haplogroups", conn, if_exists="replace", index=False)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mtdna_haplogroups (
                haplogroup TEXT, rsid TEXT, position TEXT,
                ancestral TEXT, derived TEXT, region TEXT
            )
        """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mt_rsid ON mtdna_haplogroups(rsid)")
    progress(f"  mtDNA haplogroups: {len(mt_rows)} SNP entries")

    # Process Y-DNA haplogroups
    y_rows = []
    y_data = data.get("ydna", data.get("yDNA", []))
    if isinstance(y_data, dict):
        y_data = list(y_data.values()) if not isinstance(list(y_data.values())[0], str) else [y_data]
    for entry in y_data:
        if isinstance(entry, dict):
            snps = entry.get("defining_snps", entry.get("snps", []))
            if isinstance(snps, list):
                for snp in snps:
                    if isinstance(snp, dict):
                        y_rows.append({
                            "haplogroup": entry.get("haplogroup", entry.get("name", "")),
                            "rsid": snp.get("rsid", ""),
                            "position": str(snp.get("position", "")),
                            "ancestral": snp.get("ancestral", snp.get("ref", "")),
                            "derived": snp.get("derived", snp.get("alt", "")),
                            "region": entry.get("region", entry.get("origin", "")),
                        })
                    elif isinstance(snp, str):
                        y_rows.append({
                            "haplogroup": entry.get("haplogroup", entry.get("name", "")),
                            "rsid": snp if snp.startswith("rs") else "",
                            "position": snp if not snp.startswith("rs") else "",
                            "ancestral": "",
                            "derived": "",
                            "region": entry.get("region", entry.get("origin", "")),
                        })
            elif "rsid" in entry:
                y_rows.append({
                    "haplogroup": entry.get("haplogroup", entry.get("name", "")),
                    "rsid": entry["rsid"],
                    "position": str(entry.get("position", "")),
                    "ancestral": entry.get("ancestral", entry.get("ref", "")),
                    "derived": entry.get("derived", entry.get("alt", "")),
                    "region": entry.get("region", entry.get("origin", "")),
                })

    if y_rows:
        pd.DataFrame(y_rows).to_sql("ydna_haplogroups", conn, if_exists="replace", index=False)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ydna_haplogroups (
                haplogroup TEXT, rsid TEXT, position TEXT,
                ancestral TEXT, derived TEXT, region TEXT
            )
        """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_y_rsid ON ydna_haplogroups(rsid)")
    progress(f"  Y-DNA haplogroups: {len(y_rows)} SNP entries")


def load_curated_pharma(conn):
    """Load curated pharmacogenomics data to supplement PharmGKB."""
    progress("Loading curated pharma data ...")
    data = load_json("pharma_variants.json")
    if not data:
        progress("  No curated pharma data found — skipping")
        return

    # If the curated file has entries not in PharmGKB, add them to the pharmgkb table
    rows = []
    for entry in data:
        rsid = entry.get("rsid", "")
        if not rsid:
            continue
        rows.append({
            "rsid": rsid,
            "gene": entry.get("gene", ""),
            "drug": json.dumps(entry.get("drugs", entry.get("drug", ""))) if isinstance(entry.get("drugs", entry.get("drug", "")), list) else str(entry.get("drugs", entry.get("drug", ""))),
            "phenotype_category": entry.get("phenotype", entry.get("category", "")),
            "evidence_level": entry.get("evidence_level", "curated"),
            "annotation_id": entry.get("annotation_id", ""),
            "star_allele": entry.get("star_allele", ""),
            "metabolizer_status": entry.get("metabolizer_status", ""),
            "recommendation": entry.get("recommendation", entry.get("effect", "")),
        })

    if rows:
        df = pd.DataFrame(rows)
        # Append curated data to pharmgkb table (don't replace — downloaded data is already there)
        df.to_sql("pharmgkb_curated", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pgkb_curated_rsid ON pharmgkb_curated(rsid)")
        progress(f"  Loaded {len(df)} curated pharma entries")


def load_prs_definitions(conn):
    """
    Create PRS definitions table from GWAS data.
    PRS definitions group GWAS SNPs by trait for polygenic risk scoring.
    """
    progress("Loading PRS definitions ...")

    # Check if there's a curated PRS file (preferred over GWAS-derived)
    prs_data = load_json("prs_definitions.json")
    if prs_data:
        rows = []
        for entry in prs_data:
            if isinstance(entry, dict):
                rsid = entry.get("rsid", "")
                rows.append({
                    "rsid": rsid,
                    "trait": entry.get("trait", ""),
                    "effect_allele": entry.get("effect_allele", entry.get("risk_allele", "")),
                    "effect_allele_freq": float(entry.get("effect_allele_freq", 0.5)),
                    "beta": str(entry.get("beta", entry.get("weight", ""))),
                    "source": entry.get("source", "curated"),
                })
        if rows:
            pd.DataFrame(rows).to_sql("prs_definitions", conn, if_exists="replace", index=False)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prs_rsid ON prs_definitions(rsid)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prs_trait ON prs_definitions(trait)")
            progress(f"  Loaded {len(rows)} curated PRS entries")
            return

    # Otherwise, derive from GWAS table
    try:
        gwas_df = pd.read_sql("SELECT rsid, trait, risk_allele, or_beta FROM gwas", conn)
    except Exception:
        gwas_df = pd.DataFrame()

    if len(gwas_df) == 0:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prs_definitions (
                rsid TEXT, trait TEXT, effect_allele TEXT, beta TEXT, source TEXT
            )
        """)
        progress("  No GWAS data available — created empty prs_definitions table")
        return

    # Extract effect allele from risk_allele column (format: "rs12345-A")
    def extract_allele(val):
        if pd.isna(val) or not isinstance(val, str):
            return ""
        if "-" in val:
            return val.split("-")[-1].strip()
        return ""

    records = pd.DataFrame()
    records["rsid"] = gwas_df["rsid"]
    records["trait"] = gwas_df["trait"]
    records["effect_allele"] = gwas_df["risk_allele"].apply(extract_allele)
    # Convert OR to beta (log scale) for PRS calculation
    records["beta"] = gwas_df["or_beta"].apply(
        lambda x: str(math.log(float(x))) if pd.notna(x) and float(x) > 0 else ""
    )
    records["source"] = "gwas_catalog"

    records = records[records["effect_allele"] != ""]
    records = records.drop_duplicates(subset=["rsid", "trait"])

    records.to_sql("prs_definitions", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prs_rsid ON prs_definitions(rsid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prs_trait ON prs_definitions(trait)")
    progress(f"  Derived {len(records):,} PRS definitions from GWAS data")


def load_disease_prevalence(conn):
    """Load disease prevalence data from curated JSON."""
    progress("Loading disease prevalence data ...")
    data = load_json("disease_prevalence.json")

    if not data:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS disease_prevalence (
                disease TEXT, prevalence REAL, population TEXT, source TEXT
            )
        """)
        progress("  No disease prevalence data found — created empty table")
        return

    rows = []
    for entry in data:
        if isinstance(entry, dict):
            rows.append({
                "disease": entry.get("disease", entry.get("name", entry.get("trait", ""))),
                "prevalence": float(entry.get("prevalence", 0)),
                "population": entry.get("population", "general"),
                "source": entry.get("source", "curated"),
            })

    if rows:
        df = pd.DataFrame(rows)
        df.to_sql("disease_prevalence", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prevalence_disease ON disease_prevalence(disease)")
        progress(f"  Loaded {len(df)} disease prevalence entries")
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS disease_prevalence (
                disease TEXT, prevalence REAL, population TEXT, source TEXT
            )
        """)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_database():
    """Build the complete reference database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Remove old DB if it exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        progress("Removed existing database")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    try:
        # Process downloaded sources
        process_clinvar(conn)
        process_gwas(conn)
        process_pharmgkb(conn)

        # Load curated data
        load_curated_traits(conn)
        load_curated_haplogroups(conn)
        load_curated_pharma(conn)
        load_prs_definitions(conn)
        load_disease_prevalence(conn)

        conn.commit()

        # Report summary
        progress("\n=== Database Summary ===")
        cursor = conn.cursor()
        for table in [
            "clinvar", "gwas", "pharmgkb", "pharmgkb_alleles",
            "traits", "mtdna_haplogroups", "ydna_haplogroups",
            "prs_definitions", "disease_prevalence",
        ]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                progress(f"  {table}: {count:,} rows")
            except sqlite3.OperationalError:
                progress(f"  {table}: TABLE MISSING")

        db_size = os.path.getsize(DB_PATH) / (1024 * 1024)
        progress(f"\nDatabase size: {db_size:.1f} MB")
        progress(f"Database path: {DB_PATH}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Set up the DNA Analyzer reference database")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading source files (use cached copies)",
    )
    args = parser.parse_args()

    progress("=== DNA Analyzer Database Setup ===\n")

    if not args.skip_download:
        progress("Step 1/2: Downloading source data ...")
        download_all()
    else:
        progress("Step 1/2: Skipping downloads (using cached files)")

    progress("\nStep 2/2: Building database ...")
    build_database()

    progress("\n=== Setup complete! ===")


if __name__ == "__main__":
    main()
