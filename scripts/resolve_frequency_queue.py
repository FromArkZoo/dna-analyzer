#!/usr/bin/env python3
"""Resolve the Phase-1 frequency review queue (4 common/HLA variants + ABCC11).

Manual gnomAD orientation-check (2026-06-07, every alt allele queried) found the
curated population_frequency values were ACTUALLY CORRECT. The validator's "off by
Nx" flags were false positives from allele orientation: the curated risk allele is
the major/reference allele, so gnomAD reports the complementary alt frequency. This
attaches the accurate risk-allele gnomAD frequency as additive provenance and records
the resolution. It does NOT change population_frequency.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HV = REPO / "data" / "curated" / "health_variants.json"
RETRIEVED = "2026-06-07"

RES = {
    "rs1801282": {
        "gnomad_af": 0.887,
        "freq_note": "Risk allele C (Pro12) is the COMMON allele; minor Ala12 (G) "
                     "gnomAD AF=0.113 (sas popmax 0.121). Curated 0.85 confirmed accurate.",
    },
    "rs10811661": {
        "gnomad_af": 0.854,
        "freq_note": "Risk allele T is the COMMON allele; minor C gnomAD AF=0.146 "
                     "(eas popmax 0.399). Curated 0.82 confirmed accurate.",
    },
    "rs662799": {
        "gnomad_af": 0.101,
        "freq_note": "APOA5 minus-strand; risk C(gene)=genomic G(ref). Global AF ~0.10, "
                     "nfe ~0.072. Curated 0.08 confirmed accurate.",
    },
    "rs17822931": {
        "gnomad_af": 0.835,
        "freq_note": "Risk allele C(ref, wet earwax) global AF ~0.83; minor T(dry earwax) "
                     "AF=0.166 (eas popmax 0.864). Curated 0.7 ~accurate.",
        "caveat": "Keys on the common reference allele, so fires for most users; the "
                  "wet-earwax->breast-cancer association is weak/controversial. Consider "
                  "removing or reducing visibility (product decision).",
    },
    "rs2187668": {
        "freq_note": "HLA-DQA1 lies in the MHC where gnomAD AF (0.003) is unreliable due "
                     "to mapping. Literature DQ2.5-tag (T) allele ~0.10-0.13; curated 0.14 "
                     "retained, no gnomad_af attached.",
    },
}


def main() -> int:
    hv = json.loads(HV.read_text())
    patched = []
    for e in hv:
        rs = e.get("rsid")
        if rs in RES:
            r = RES[rs]
            if "gnomad_af" in r:
                e["gnomad_af"] = r["gnomad_af"]
                e["gnomad_af_source"] = (f"gnomAD v4 joint, manual orientation-check via "
                                         f"GDM science-skills, {RETRIEVED}")
            e["freq_note"] = r["freq_note"]
            if "caveat" in r:
                e["caveat"] = r["caveat"]
            e["freq_review_resolved"] = RETRIEVED
            patched.append(rs)
        patched_out = e
    shutil.copy2(HV, HV.with_suffix(".json.bak"))
    HV.write_text(json.dumps(hv, indent=2, ensure_ascii=False) + "\n")
    print(f"Patched {len(patched)} entries: {patched}")
    print(f"Wrote {HV} (backup .json.bak)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
