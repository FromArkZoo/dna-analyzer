#!/usr/bin/env python3
"""Pharmacogenomics-panel audit remediation: 3 fixes + 5 removals.

A star-allele audit (claimed amino-acid substitution vs VEP, gene vs dbSNP) across
the pharma panel found 8 confirmed errors. The many other flags were VEP
multi-allelic artifacts on correct textbook star alleles (e.g. CYP2C9*2 R144C,
TPMT*3B A154T) or intentional HLA/cluster tag-SNP labels (HCP5, IFNL3/4, UGT1A),
all left untouched. Each fix/removal below was verified against dbSNP.
"""
import json
from pathlib import Path

CUR = Path(__file__).resolve().parent.parent / "data" / "curated"

# wrong rsID for the claimed star allele; corrected (dbSNP/VEP-verified, not duplicates)
SWAP = {
    "rs3093105": "rs2108622",   # CYP4F2 *3 (V433M) — rs3093105 was a different CYP4F2 variant
    "rs4986913": "rs4987161",   # CYP3A4 *17 (F189S) — rs4986913 was a different CYP3A4 variant
}
# wrong rsID AND the correct variant is already in the set (duplicate), or vague/wrong-gene
REMOVE = {
    "rs4803419",   # CYP2C19*4 already present as rs28399504; rs4803419 is in CYP2B6
    "rs7668258",   # VKORC1 -1639 already present as rs9923231; rs7668258 is in UGT2B7
    "rs12720461",  # DPYD already covered by *2A/*13; this "promoter" rsID is in CYP1A2
    "rs4633",      # COMT V158M is rs4680 (already in set); rs4633 is synonymous H62H
    "rs2725264",   # vague CYP2C19 "tag"; actually ABCG2
}


def relabel_7900194(e):
    """rs7900194 IS CYP2C9 R150H (= *8); it was mislabeled *11B / R150L. Correct in place."""
    e["star_allele"] = "*8"
    for k, v in list(e.items()):
        if isinstance(v, str):
            e[k] = (v.replace("*11B", "*8").replace("Arg150Leu", "Arg150His")
                    .replace("R150L", "R150H").replace("150Leu", "150His"))
    return e


def main():
    all_old = set(SWAP) | REMOVE
    new_ids = set(SWAP.values())

    existing = set()
    for f in ("health_variants.json", "trait_variants.json", "prs_definitions.json",
              "pharma_variants.json", "ancestry_markers.json"):
        existing |= {x.get("rsid") for x in json.loads((CUR / f).read_text())}
    clash = new_ids & existing
    if clash:
        raise SystemExit(f"ABORT: replacement rsID already present: {clash}")

    pharma = []
    for e in json.loads((CUR / "pharma_variants.json").read_text()):
        rs = e.get("rsid")
        if rs in REMOVE:
            print(f"REMOVE  {rs} ({e.get('gene')} {e.get('star_allele')})")
            continue
        if rs in SWAP:
            e["rsid"] = SWAP[rs]
            print(f"SWAP    {rs} -> {e['rsid']} ({e.get('gene')} {e.get('star_allele')})")
        if rs == "rs7900194":
            relabel_7900194(e)
            print(f"RELABEL rs7900194 -> star {e['star_allele']} (CYP2C9 R150H/*8)")
        pharma.append(e)
    (CUR / "pharma_variants.json").write_text(json.dumps(pharma, indent=2, ensure_ascii=False) + "\n")

    for name in ("alphagenome_scores.json", "vep_annotations.json"):
        arr = [r for r in json.loads((CUR / name).read_text()) if r.get("rsid") not in all_old]
        (CUR / name).write_text(json.dumps(arr, indent=2, ensure_ascii=False) + "\n")
    print(f"\nRemoved {sorted(all_old)} from enrichment files. Re-enrich: {sorted(new_ids)}")


if __name__ == "__main__":
    main()
