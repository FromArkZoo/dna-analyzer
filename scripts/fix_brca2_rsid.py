#!/usr/bin/env python3
"""One-off correction: rs28897696 -> rs80359550 for "BRCA2 6174delT".

The curated entry named the Ashkenazi BRCA2 founder deletion "BRCA2 6174delT" but
carried the rsID rs28897696 — which is actually an unrelated BRCA1 missense VUS on
chr17 (verified via dbSNP/VEP/ClinVar: chr17 vs BRCA2's chr13, SNV vs deletion).
The intended variant is rs80359550 (BRCA2, chr13, the delT, ClinVar Pathogenic).

This corrects the rsID, strips the stale (BRCA1) provenance, re-fetches fresh
ClinVar + gnomAD for rs80359550, and removes the orphaned rs28897696 from the
AlphaGenome + VEP enrichment files (the scorers then re-add rs80359550).
"""
import json
import subprocess
from pathlib import Path

SK = Path.home() / "science-skills" / "skills"
REPO = Path(__file__).resolve().parent.parent
HV = REPO / "data" / "curated" / "health_variants.json"
OLD, NEW = "rs28897696", "rs80359550"


def run(skill, args):
    subprocess.run(["uv", "run", *args, "--output", "/tmp/fix.json"],
                   cwd=SK / skill, capture_output=True, text=True, timeout=180)
    try:
        return json.loads(Path("/tmp/fix.json").read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return None


hv = json.loads(HV.read_text())
e = next(x for x in hv if x["rsid"] == OLD)
e["rsid"] = NEW
for k in ("clinvar_xref", "gnomad_af", "gnomad_af_popmax", "gnomad_af_popmax_pop", "gnomad_af_source"):
    e.pop(k, None)

# fresh ClinVar for the correct variant
cvs = run("clinvar_database", ["scripts/clinvar_api.py", "search", "--query", NEW, "--retmax", "5"]) or {}
vids = cvs.get("variant_ids") or []
if vids:
    summ = run("clinvar_database", ["scripts/clinvar_api.py", "summary", "--variant_ids", vids[0]])
    if summ:
        s0 = summ[0]
        e["clinvar_xref"] = {"classification": s0.get("clinical_significance"),
                             "review_status": s0.get("review_status"),
                             "last_evaluated": s0.get("last_evaluated"),
                             "retrieved": "2026-06-08"}

# fresh gnomAD (deletion; by-rsID, rsID-confirmed)
gn = run("gnomad_database", ["scripts/get_variant_frequency.py", "--rsid", NEW]) or {}
v = (gn.get("data", {}) or {}).get("variant") or {}
if NEW.lower() in [str(x).lower() for x in (v.get("rsids") or [])]:
    joint = v.get("joint") or {}
    ac, an = joint.get("ac"), joint.get("an")
    af = (ac / an) if ac and an else None
    if af is not None:
        faf = joint.get("faf95") or {}
        e["gnomad_af"] = af
        e["gnomad_af_popmax"] = faf.get("popmax")
        e["gnomad_af_popmax_pop"] = faf.get("popmax_population")
        e["gnomad_af_source"] = "gnomAD v4 joint (by-rsID, rsID-confirmed via GDM science-skills), retrieved 2026-06-08"

HV.write_text(json.dumps(hv, indent=2, ensure_ascii=False) + "\n")

# drop the orphaned OLD rsID from the enrichment files (scorers re-add NEW)
for name in ("alphagenome_scores.json", "vep_annotations.json"):
    p = REPO / "data" / "curated" / name
    arr = [r for r in json.loads(p.read_text()) if r.get("rsid") != OLD]
    p.write_text(json.dumps(arr, indent=2, ensure_ascii=False) + "\n")

print("Corrected entry:")
print(json.dumps({k: e.get(k) for k in
                  ("rsid", "gene", "variant_name", "significance", "severity",
                   "clinvar_xref", "gnomad_af", "gnomad_af_popmax_pop")}, indent=2))
print(f"\nRemoved {OLD} from alphagenome_scores.json + vep_annotations.json.")
