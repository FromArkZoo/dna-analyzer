"""Loader for pre-computed Ensembl VEP molecular-consequence annotations (Phase 2).

Pure local lookup of data/curated/vep_annotations.json (built offline by
scripts/vep_annotate_curated.py). No runtime API calls — the offline/privacy
guarantee is preserved. Complements the AlphaGenome regulatory view with the
coding/protein view (consequence + AlphaMissense for missense variants).
"""
import json
import logging
import os

from config import CURATED_DIR

logger = logging.getLogger(__name__)

_VEP = None  # lazy cache: {rsid_lower: annotation}


def _load() -> dict:
    global _VEP
    if _VEP is None:
        path = os.path.join(CURATED_DIR, "vep_annotations.json")
        try:
            with open(path) as f:
                _VEP = {r["rsid"].lower(): r for r in json.load(f)
                        if r.get("status") == "ok" and r.get("rsid")}
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            logger.info("VEP annotations not available; skipping consequence annotations")
            _VEP = {}
    return _VEP


def get_consequence(rsid):
    """Return a display-ready VEP consequence summary for an rsID, or None."""
    if not rsid:
        return None
    r = _load().get(str(rsid).lower())
    if not r or not r.get("consequence"):
        return None
    am = r.get("alphamissense") or {}
    return {
        "consequence": str(r["consequence"]).replace("_", " "),
        "impact": r.get("impact"),
        "amino_acids": r.get("amino_acids"),
        "alphamissense_class": (str(am["class"]).replace("_", " ") if am.get("class") else None),
        "alphamissense_score": am.get("score"),
        "sift": r.get("sift"),
        "polyphen": r.get("polyphen"),
        "source": "Ensembl VEP",
    }
