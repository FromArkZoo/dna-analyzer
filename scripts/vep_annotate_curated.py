#!/usr/bin/env python3
"""Phase 2: annotate curated variants with Ensembl VEP (molecular consequence).

BUILD-TIME ONLY, OFFLINE PRE-COMPUTE. For each curated variant rsID, runs Ensembl
VEP (via the GDM science-skills wrapper; free public API, no key) and stores a
compact per-variant summary — most-severe consequence, and for the representative
transcript: amino-acid change, AlphaMissense class/score, SIFT, PolyPhen, LOEUF —
to data/curated/vep_annotations.json. Queries public reference variants by rsID,
never user genotypes; the app reads only the local JSON at runtime.

Resumable: re-running continues from non-'ok' entries.

Run:
    cd ~/science-skills/skills/ensembl_database
    uv run scripts/ensembl_api.py --help   # (skill provides VEP)
    python ~/dna-analyzer/scripts/vep_annotate_curated.py
"""
import json
import os
import subprocess
import time
from pathlib import Path

REPO = Path(os.path.expanduser("~/dna-analyzer"))
CUR = REPO / "data" / "curated"
OUT = CUR / "vep_annotations.json"
ENSEMBL_DIR = Path(os.path.expanduser("~/science-skills/skills/ensembl_database"))


def vep_get(rsid):
    r = subprocess.run(["uv", "run", "scripts/ensembl_api.py", "vep", rsid, "--species", "human",
                        "--output", "/tmp/vep_curated.json"],
                       cwd=ENSEMBL_DIR, capture_output=True, text=True, timeout=90)
    if r.returncode != 0:
        return None
    try:
        d = json.loads(Path("/tmp/vep_curated.json").read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return None
    return d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else None)


def summarize(vep, genes):
    """Pick a representative transcript and extract a compact consequence summary."""
    most = vep.get("most_severe_consequence")
    tc = vep.get("transcript_consequences") or []
    cands = [t for t in tc if most in (t.get("consequence_terms") or [])] or tc
    gene_cands = [t for t in cands if t.get("gene_symbol") in genes] or cands
    if not gene_cands:
        return {"consequence": most}
    rep = next((t for t in gene_cands if t.get("alphamissense")), gene_cands[0])
    out = {"consequence": most, "gene": rep.get("gene_symbol"), "impact": rep.get("impact")}
    if rep.get("amino_acids"):
        out["amino_acids"] = rep["amino_acids"]
    am = rep.get("alphamissense") or {}
    if am:
        out["alphamissense"] = {"class": am.get("am_class"), "score": am.get("am_pathogenicity")}
    for k_src, k_dst in (("sift_prediction", "sift"), ("polyphen_prediction", "polyphen")):
        if rep.get(k_src):
            out[k_dst] = rep[k_src]
    if rep.get("loeuf") is not None:
        out["loeuf"] = rep["loeuf"]
    return out


def collect_curated():
    want = {}

    def add(rs, gene):
        if not rs or not str(rs).startswith("rs"):
            return
        w = want.setdefault(rs, {"rsid": rs, "genes": set()})
        if gene:
            w["genes"].add(gene)

    def load(name):
        p = CUR / name
        return json.loads(p.read_text()) if p.exists() else []

    for name, gk in [("health_variants.json", "gene"), ("trait_variants.json", "gene"),
                     ("prs_definitions.json", "gene"), ("pharma_variants.json", "gene"),
                     ("ancestry_markers.json", "gene")]:
        for e in load(name):
            add(e.get("rsid"), e.get(gk))
    return want


def main():
    want = collect_curated()
    done = {}
    if OUT.exists():
        done = {r["rsid"]: r for r in json.loads(OUT.read_text())}
    ok_done = {rs for rs, r in done.items() if r.get("status") == "ok"}
    todo = [rs for rs in want if rs not in ok_done]
    limit = int(os.environ.get("VEP_LIMIT", "0") or 0)
    if limit:
        todo = todo[:limit]
    print(f"{len(want)} unique curated rsIDs | {len(ok_done)} already ok | {len(todo)} to annotate", flush=True)
    results = [r for r in done.values() if r.get("status") == "ok"]

    for i, rs in enumerate(todo, 1):
        info = want[rs]
        rec = {"rsid": rs, "genes": sorted(info["genes"])}
        try:
            vep = vep_get(rs)
            if not vep:
                rec["status"] = "skipped (no VEP result)"
            else:
                rec.update(summarize(vep, info["genes"]))
                rec["status"] = "ok"
        except Exception as e:  # noqa: BLE001
            rec["status"] = f"error: {type(e).__name__}: {str(e)[:120]}"
        results.append(rec)
        if i % 10 == 0 or i == len(todo):
            OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
            ok = sum(1 for r in results if r.get("status") == "ok")
            print(f"[{i}/{len(todo)}] {rs} -> {rec.get('status')}  (saved; {ok} ok)", flush=True)
        time.sleep(0.15)

    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    ok = [r for r in results if r.get("status") == "ok"]
    from collections import Counter
    cons = Counter(r.get("consequence") for r in ok)
    print(f"\nDONE. {len(results)} variants -> {OUT}  ({len(ok)} ok)")
    print("consequence distribution:", dict(cons.most_common(10)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
