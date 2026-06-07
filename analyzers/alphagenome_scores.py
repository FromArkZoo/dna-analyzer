"""Loader for pre-computed AlphaGenome regulatory scores (Phase 3).

Reads data/curated/alphagenome_scores.json (built offline, build-time, by
scripts/alphagenome_score_curated.py) and exposes get_regulatory(rsid), returning
a display-ready summary or None. This is a pure local lookup — NO external API
calls at runtime, so the app's offline/privacy guarantee is preserved.
"""
import json
import logging
import os

from config import CURATED_DIR

logger = logging.getLogger(__name__)

_SCORES = None  # lazy cache: {rsid_lower: summary}

# A neighbouring-gene effect (top_expr without an own-gene match) is only shown
# when its quantile is in the extreme tail, since single-track attribution is noisy.
_NEARBY_MIN_QUANTILE = 0.99
_SPLICE_MIN_RAW = 0.05


def _load() -> dict:
    global _SCORES
    if _SCORES is None:
        path = os.path.join(CURATED_DIR, "alphagenome_scores.json")
        try:
            with open(path) as f:
                _SCORES = {r["rsid"].lower(): r for r in json.load(f)
                           if r.get("status") == "ok" and r.get("rsid")}
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            logger.info("AlphaGenome scores not available; skipping regulatory annotations")
            _SCORES = {}
    return _SCORES


def get_regulatory(rsid):
    """Return a display-ready regulatory summary for an rsID, or None.

    Prefers the variant's OWN annotated gene (reliable, gene-matched). Falls back
    to the top single-track gene only when its effect is in the extreme tail, and
    flags it as a neighbouring gene (single-track attribution is less reliable).
    """
    if not rsid:
        return None
    s = _load().get(str(rsid).lower())
    if not s:
        return None

    own, top = s.get("own_gene"), s.get("top_expr")
    if own and own.get("gene"):
        src, nearby = own, False
    elif top and top.get("gene") and abs(top.get("quantile") or 0) >= _NEARBY_MIN_QUANTILE:
        src, nearby = top, True
    else:
        return None

    q = src.get("quantile") or 0.0
    by_mod = s.get("max_raw_by_modality") or {}
    return {
        "gene": src.get("gene"),
        "tissue": src.get("tissue"),
        "direction": "decreased" if q < 0 else "increased",
        "quantile": round(q, 3),
        "effect_size": src.get("raw"),
        "nearby_gene": nearby,
        "affects_splicing": (by_mod.get("SPLICE_SITES") or 0) > _SPLICE_MIN_RAW,
        "source": "AlphaGenome (Google DeepMind), pre-computed offline",
    }
