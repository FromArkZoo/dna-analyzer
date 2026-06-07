#!/usr/bin/env python3
"""Apply reviewed Phase-1 reference corrections to health_variants.json.

Applies ONLY changes agreed in review:
  1. Tier A significance fixes — driven by `severity`, because that is the field
     analyzers/health_risks.py actually reads (not `significance`).
  2. clinvar_xref provenance on every entry that has a current ClinVar classification
     (keeps your risk-factor framing; records what ClinVar says alongside it).
  3. ADDITIVE gnomAD frequency fields (gnomad_af / gnomad_af_popmax / source).
     Does NOT overwrite population_frequency, which still feeds calculate_absolute_risk
     as a disease baseline — that conflation is a separate Phase-4 fix.

Usage:
    python scripts/apply_validation_fixes.py            # dry-run (default)
    python scripts/apply_validation_fixes.py --apply    # write (creates .bak)
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HV = REPO / "data" / "curated" / "health_variants.json"
VAL = REPO / "data" / "validation" / "health_variants_validation.json"
RETRIEVED = "2026-06-07"

# ---- Tier A: reviewed significance decisions -------------------------------
REMOVE = {
    # BRCA2: ClinVar Benign (reviewed by expert panel) + gnomAD ~0.6% — far too common
    # for a high-penetrance pathogenic call. Was flagged CRITICAL → false positive.
    "rs28897727": "ClinVar Benign (expert panel) + gnomAD ~0.6%; false-positive CRITICAL",
}
RECLASSIFY = {
    # PCSK9 R46L: a protective loss-of-function allele (lowers LDL-C, reduces CHD risk),
    # not pathogenic. ClinVar: Benign/Likely benign.
    "rs11591147": {
        "significance": "Protective",
        "severity": "PROTECTIVE",
        "odds_ratio": 0.6,
        "note": ("Reclassified %s: PCSK9 R46L is a protective loss-of-function allele "
                 "(lowers LDL-C, reduces coronary disease risk). ClinVar: Benign/Likely benign."
                 % RETRIEVED),
    },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = ap.parse_args()

    hv = json.loads(HV.read_text())
    val = {r["rsid"]: r for r in json.loads(VAL.read_text())}

    out, changes, review_queue = [], [], []
    n_xref = n_freq = 0
    for e in hv:
        rs = e.get("rsid")
        if rs in REMOVE:
            changes.append(f"REMOVE   {rs} ({e.get('gene')}): {REMOVE[rs]}")
            continue

        v = val.get(rs, {})

        if rs in RECLASSIFY:
            before = f"{e.get('severity')}/{e.get('significance')}"
            e.update(RECLASSIFY[rs])
            changes.append(f"RECLASS  {rs} ({e.get('gene')}): {before} -> "
                           f"{e['severity']}/{e['significance']}")

        if v.get("clinvar_significance"):
            e["clinvar_xref"] = {
                "classification": v.get("clinvar_significance"),
                "review_status": v.get("clinvar_review_status"),
                "last_evaluated": v.get("clinvar_last_evaluated"),
                "retrieved": RETRIEVED,
            }
            n_xref += 1

        af = v.get("gnomad_global_af")
        cur = e.get("population_frequency")
        if v.get("gnomad_confirmed") and not v.get("gnomad_af_suspect") and isinstance(af, (int, float)):
            gene = (e.get("gene") or "").upper()
            # Auto-attach ONLY for rare, orientation-unambiguous alleles. Common variants
            # (AF >= 0.05) can be major/minor flips that rsID-confirmation can't detect;
            # MHC/HLA gnomAD mappings are unreliable. Those go to the review queue.
            if af < 0.05 and not gene.startswith("HLA"):
                e["gnomad_af"] = af
                e["gnomad_af_popmax"] = v.get("gnomad_popmax_faf95")
                e["gnomad_af_popmax_pop"] = v.get("gnomad_popmax_pop")
                e["gnomad_af_source"] = (f"gnomAD v4 joint (allele-pinned, rsID-confirmed via "
                                         f"GDM science-skills), retrieved {RETRIEVED}")
                n_freq += 1
            elif isinstance(cur, (int, float)) and cur > 0 and max(cur / af, af / cur) > 5:
                reason = "MHC/HLA mapping unreliable" if gene.startswith("HLA") else \
                    ("possible major/minor or strand flip (AF≈1−curated)"
                     if abs(af - (1 - cur)) < 0.3 * (1 - cur) else "common-variant allele orientation unverified")
                review_queue.append({
                    "rsid": rs, "gene": e.get("gene"), "curated_freq": cur,
                    "gnomad_af_pinned": af, "popmax": v.get("gnomad_popmax_faf95"),
                    "popmax_pop": v.get("gnomad_popmax_pop"), "reason": reason,
                })

        out.append(e)

    print(f"Entries: {len(hv)} -> {len(out)}  ({len(REMOVE)} removed)")
    print(f"clinvar_xref added: {n_xref}    gnomad_af auto-attached (rare/unambiguous): {n_freq}")
    print(f"frequency review queue (common/HLA, NOT auto-applied): {len(review_queue)}\n")
    print("Tier A changes:")
    for c in changes:
        print("  " + c)
    if review_queue:
        print("\nFrequency review queue:")
        for q in review_queue:
            print(f"  {q['rsid']:12} {q['gene']:10} cur={q['curated_freq']} pinned={q['gnomad_af_pinned']:.3g} :: {q['reason']}")

    if args.apply:
        shutil.copy2(HV, HV.with_suffix(".json.bak"))
        HV.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
        (REPO / "data" / "validation" / "frequency_review_queue.json").write_text(
            json.dumps(review_queue, indent=2) + "\n")
        print(f"\nWROTE {HV}  (backup at {HV.with_suffix('.json.bak').name})")
        print(f"WROTE data/validation/frequency_review_queue.json ({len(review_queue)} items)")
    else:
        print("\n(dry-run — re-run with --apply to write; a .bak will be created)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
