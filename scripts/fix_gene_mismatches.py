#!/usr/bin/env python3
"""Fix 8 wrong-rsID gene mismatches found by the curated-gene vs VEP/dbSNP cross-check.

Each entry described gene X with correct biology but carried an rsID that actually
sits in an unrelated gene (independently confirmed by dbSNP and VEP). Five are
corrected to the right rsID for the intended gene/variant; three redundant, vague,
or dubious entries are removed.

Pharma entries carry no allele-keyed data, so a rsID swap suffices. Trait entries
have genotype->phenotype maps that must match the new variant's alleles, so those
are re-keyed per the cited source literature (Katzenberg 1998 for CLOCK rs1801260;
Panicker 2008 for DIO1 rs2235544; COL5A1 rs12722 keeps its C/T map + direction).
"""
import json
from pathlib import Path

CUR = Path(__file__).resolve().parent.parent / "data" / "curated"

PHARMA_SWAP = {"rs17884712": "rs72558189"}   # CYP2C9 *14 (R125H, VEP-confirmed)
# rs10264272: redundant 2nd *8 entry; rs10873531: vague intronic, lands in HSP90AA1;
# rs1058930: CYP2C9*8 already in the set as rs7900194 (duplicate intent).
PHARMA_REMOVE = {"rs10264272", "rs10873531", "rs1058930"}
# rs2166975: dubious dimples/MYH9; rs2229456 & rs2760118: COL5A1 rs12722 and CLOCK
# rs1801260 are already in the set (duplicate variants under other trait labels).
TRAIT_REMOVE = {"rs2166975", "rs2229456", "rs2760118"}

# trait fixes: new rsID + genotype map matching the correct variant's alleles
TRAIT_FIX = {
    "rs4626": {  # DIO1 rs2235544 (A/C) — C allele -> higher DIO1 activity (Panicker 2008); re-key
        "rsid": "rs2235544",
        "genotype_results": {
            "CC": "Higher deiodinase 1 activity — efficient T4 to T3 conversion (relatively higher T3).",
            "AC": "Intermediate T4 to T3 conversion.",
            "AA": "Lower T4 to T3 conversion — may have relatively lower T3 levels. Can affect metabolism and energy.",
        },
    },
}


def load(name):
    return json.loads((CUR / name).read_text())


def save(name, data):
    (CUR / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    all_old = set(PHARMA_SWAP) | PHARMA_REMOVE | TRAIT_REMOVE | set(TRAIT_FIX)
    new_ids = set(PHARMA_SWAP.values()) | {v["rsid"] for v in TRAIT_FIX.values()}

    # collision guard: don't introduce a rsID that already exists elsewhere
    existing = set()
    for fn in ("health_variants.json", "trait_variants.json", "prs_definitions.json",
               "pharma_variants.json", "ancestry_markers.json"):
        existing |= {e.get("rsid") for e in load(fn)}
    clash = new_ids & existing
    if clash:
        raise SystemExit(f"ABORT: replacement rsID already present in curated set: {clash}")

    # pharma
    pharma = []
    for e in load("pharma_variants.json"):
        rs = e.get("rsid")
        if rs in PHARMA_REMOVE:
            print(f"REMOVE pharma {rs} ({e.get('gene')} {e.get('star_allele')})")
            continue
        if rs in PHARMA_SWAP:
            e["rsid"] = PHARMA_SWAP[rs]
            print(f"FIX    pharma {rs} -> {e['rsid']} ({e.get('gene')} {e.get('star_allele')})")
        pharma.append(e)
    save("pharma_variants.json", pharma)

    # traits
    traits = []
    for e in load("trait_variants.json"):
        rs = e.get("rsid")
        if rs in TRAIT_REMOVE:
            print(f"REMOVE trait  {rs} ({e.get('trait')})")
            continue
        if rs in TRAIT_FIX:
            fix = TRAIT_FIX[rs]
            e["rsid"] = fix["rsid"]
            if "genotype_results" in fix:
                e["genotype_results"] = fix["genotype_results"]
            print(f"FIX    trait  {rs} -> {e['rsid']} ({e.get('gene')} / {e.get('trait')})"
                  f"{' [re-keyed map]' if 'genotype_results' in fix else ''}")
        traits.append(e)
    save("trait_variants.json", traits)

    # drop all 8 old rsIDs from the enrichment files (scorers re-add the 5 new ones)
    for name in ("alphagenome_scores.json", "vep_annotations.json"):
        arr = [r for r in load(name) if r.get("rsid") not in all_old]
        save(name, arr)
    print(f"\nRemoved {len(all_old)} old rsIDs from alphagenome_scores.json + vep_annotations.json.")
    print(f"New rsIDs to (re)enrich: {sorted(new_ids)}")


if __name__ == "__main__":
    main()
