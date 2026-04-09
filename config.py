"""Configuration constants for the DNA Analyzer application."""

import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "reference.db")
DOWNLOADS_DIR = os.path.join(DATA_DIR, "downloads")
CURATED_DIR = os.path.join(DATA_DIR, "curated")

# Reference genome assembly
ASSEMBLY = "GRCh37"

# Severity levels with display colors
SEVERITY_LEVELS = {
    "CRITICAL":   {"rank": 0, "color": "#DC2626", "label": "Critical"},
    "HIGH":       {"rank": 1, "color": "#EA580C", "label": "High"},
    "MODERATE":   {"rank": 2, "color": "#CA8A04", "label": "Moderate"},
    "LOW":        {"rank": 3, "color": "#2563EB", "label": "Low"},
    "PROTECTIVE": {"rank": 4, "color": "#16A34A", "label": "Protective"},
}

# ClinVar clinical significance categories considered pathogenic
PATHOGENIC_SIGNIFICANCES = [
    "Pathogenic",
    "Likely pathogenic",
    "Pathogenic/Likely pathogenic",
]

# GWAS significance threshold
GWAS_P_VALUE_THRESHOLD = 5e-8

# Data source URLs
CLINVAR_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
GWAS_CATALOG_URL = "https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest/gwas-catalog-associations-full.zip"
PHARMGKB_URL = "https://api.pharmgkb.org/v1/download/file/data/clinicalAnnotations.zip"

# Flask settings
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
