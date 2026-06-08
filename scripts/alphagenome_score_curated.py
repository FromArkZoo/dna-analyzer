#!/usr/bin/env python3
"""Phase 3: pre-compute AlphaGenome regulatory scores for curated variants.

BUILD-TIME ONLY, OFFLINE PRE-COMPUTE. Scores each curated variant (a fixed,
public marker set — never user genotypes) through AlphaGenome's regulatory
scorers, aggregates the thousands of per-track scores into a compact per-variant
summary, and writes data/curated/alphagenome_scores.json. The Flask app reads
that JSON at runtime; no live API calls, so the offline/privacy guarantee holds.

Resumable: re-running continues where it left off (skips rsIDs already in the
output). Per-variant errors are recorded, not fatal.

Run inside the AlphaGenome skill's uv env:
    cd ~/science-skills/skills/alphagenome_single_variant_analysis
    uv run --project . ~/dna-analyzer/scripts/alphagenome_score_curated.py
"""
import json
import os
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env"))

REPO = Path(os.path.expanduser("~/dna-analyzer"))
CUR = REPO / "data" / "curated"
OUT = CUR / "alphagenome_scores.json"
DBSNP_DIR = Path(os.path.expanduser("~/science-skills/skills/dbsnp_database"))
GNOMAD_DIR = Path(os.path.expanduser("~/science-skills/skills/gnomad_database"))
COMP = {"A": "T", "T": "A", "C": "G", "G": "C"}
SCORER_NAMES = ["RNA_SEQ", "DNASE", "CHIP_HISTONE", "SPLICE_SITES"]  # CONTACT_MAPS excluded (gRPC INTERNAL)

from alphagenome.data import genome
from alphagenome.models import dna_client, variant_scorers

MODEL = dna_client.create(api_key=os.environ["ALPHAGENOME_API_KEY"],
                          address="dns:///gdmscience.googleapis.com:443")
REC = variant_scorers.RECOMMENDED_VARIANT_SCORERS
SCORERS = [REC[n] for n in SCORER_NAMES if n in REC]


def dbsnp_get(rsid):
    subprocess.run(["uv", "run", "scripts/dbsnp_cli.py", "get-variant", rsid, "--output", "/tmp/agb_db.json"],
                   cwd=DBSNP_DIR, capture_output=True, text=True, timeout=60)
    return json.loads(Path("/tmp/agb_db.json").read_text())


def gnomad_indel_vcf(rsid):
    """Return VCF-normalized (chrom, pos, ref, alt) for an indel via gnomAD, or None.

    gnomAD's variant_id is already left-aligned VCF (anchor-base) form, which is
    what AlphaGenome's genome.Variant expects. rsID-CONFIRMED: the by-rsID lookup
    can return a neighbouring/absent variant (e.g. rs1799752 -> F508del), so we
    only trust it when the returned record actually carries our rsID.
    """
    subprocess.run(["uv", "run", "scripts/get_variant_frequency.py", "--rsid", rsid, "--output", "/tmp/agb_gn.json"],
                   cwd=GNOMAD_DIR, capture_output=True, text=True, timeout=60)
    try:
        v = (json.loads(Path("/tmp/agb_gn.json").read_text()).get("data", {}) or {}).get("variant") or {}
    except (json.JSONDecodeError, FileNotFoundError):
        return None
    rsids = [str(x).lower() for x in (v.get("rsids") or [])]
    if rsid.lower() not in rsids:
        return None
    parts = (v.get("variant_id") or "").split("-")
    if len(parts) != 4:
        return None
    chrom, pos, ref, alt = parts
    if not (ref and alt and set(ref + alt) <= set("ACGT")):
        return None
    return chrom, int(pos), ref, alt


def seq_chrom(seq):
    n = int(seq.split(".")[0].replace("NC_", ""))
    return {23: "X", 24: "Y"}.get(n, str(n))


def snv_placement(db):
    if (db.get("variant_type") or "") != "snv":
        return None
    for p in db.get("placements") or []:
        if not p.get("seq_id", "").startswith("NC_"):
            continue
        alleles = p.get("alleles") or []
        ref = next((a.get("deleted_sequence") for a in alleles if a.get("deleted_sequence")), None)
        pos = next((a.get("position") for a in alleles if a.get("position") is not None), None)
        alts = [a.get("inserted_sequence") for a in alleles
                if a.get("is_variant") and a.get("inserted_sequence") != a.get("deleted_sequence")]
        if ref and pos is not None and alts:
            return seq_chrom(p["seq_id"]), pos + 1, ref, alts  # SPDI 0-based -> VCF 1-based
    return None


def pick_alt(ref, alts, candidate_alleles):
    for a in candidate_alleles:
        if a in alts and a != ref:
            return a, "curated"
        c = COMP.get(a)
        if c and c in alts and c != ref:
            return c, "curated(comp)"
    return (alts[0], "first-alt") if alts else (None, None)


def summarize(df, genes):
    """Aggregate per-track scores into a per-variant summary.

    Avoids the max-over-thousands-of-tracks saturation (which makes every variant
    look 'strong'). Reports effect MAGNITUDE (|raw_score|, the predicted log2 fold
    change) plus a gene-centric view: the variant's own annotated gene and the top
    expression hit. Ranking/flagging is done relatively, downstream, on max_expr_raw.
    """
    df = df.dropna(subset=["quantile_score", "raw_score"]).copy()
    if df.empty:
        return {"n_scores": 0}
    df["absq"] = df["quantile_score"].abs()
    df["absr"] = df["raw_score"].abs()
    out = {"n_scores": int(len(df))}
    expr = df[df["output_type"] == "RNA_SEQ"].dropna(subset=["gene_name"])
    if len(expr):
        t = expr.loc[expr["absq"].idxmax()]
        out["top_expr"] = {"gene": t["gene_name"], "tissue": t.get("biosample_name"),
                           "quantile": round(float(t["quantile_score"]), 3),
                           "raw": round(float(t["raw_score"]), 4)}
        out["max_expr_raw"] = round(float(expr["absr"].max()), 4)
        out["n_expr_q99"] = int((expr["absq"] > 0.99).sum())
        og = expr[expr["gene_name"].isin(genes)] if genes else expr.iloc[0:0]
        if len(og):
            r = og.loc[og["absq"].idxmax()]
            out["own_gene"] = {"gene": r["gene_name"], "tissue": r.get("biosample_name"),
                               "quantile": round(float(r["quantile_score"]), 3),
                               "raw": round(float(r["raw_score"]), 4)}
    out["max_raw_by_modality"] = {m: round(float(g["absr"].max()), 4) for m, g in df.groupby("output_type")}
    return out


def collect_curated():
    want = {}

    def add(rs, gene, allele, src):
        if not rs or not str(rs).startswith("rs"):
            return
        w = want.setdefault(rs, {"rsid": rs, "genes": set(), "alleles": set(), "sources": set()})
        if gene:
            w["genes"].add(gene)
        if allele and str(allele).upper() in ("A", "C", "G", "T"):
            w["alleles"].add(str(allele).upper())
        w["sources"].add(src)

    def load(name):
        p = CUR / name
        return json.loads(p.read_text()) if p.exists() else []

    for e in load("health_variants.json"):
        add(e.get("rsid"), e.get("gene"), e.get("risk_allele"), "health")
    for e in load("trait_variants.json"):
        for ch in set("".join((e.get("genotype_results") or {}).keys())):
            add(e.get("rsid"), e.get("gene"), ch, "trait")
        add(e.get("rsid"), e.get("gene"), None, "trait")
    for e in load("prs_definitions.json"):
        add(e.get("rsid"), e.get("gene"), e.get("effect_allele"), "prs")
    for e in load("pharma_variants.json"):
        add(e.get("rsid"), e.get("gene"), None, "pharma")
    for e in load("ancestry_markers.json"):
        add(e.get("rsid"), e.get("gene"), e.get("effect_allele"), "ancestry")
    return want


def main():
    want = collect_curated()
    done = {}
    if OUT.exists():
        done = {r["rsid"]: r for r in json.loads(OUT.read_text())}
    ok_done = {rs for rs, r in done.items() if r.get("status") == "ok"}
    todo = [rs for rs in want if rs not in ok_done]  # re-attempt anything not yet 'ok'
    limit = int(os.environ.get("AGB_LIMIT", "0") or 0)
    if limit:
        todo = todo[:limit]
    print(f"{len(want)} unique curated rsIDs | {len(ok_done)} already ok | {len(todo)} to (re)score", flush=True)
    results = [r for r in done.values() if r.get("status") == "ok"]  # keep ok; re-do the rest

    for i, rs in enumerate(todo, 1):
        info = want[rs]
        rec = {"rsid": rs, "genes": sorted(info["genes"]), "sources": sorted(info["sources"])}
        try:
            place = snv_placement(dbsnp_get(rs))
            chrom = pos = ref = alt = how = None
            if place:
                chrom, pos, ref, alts = place
                alt, how = pick_alt(ref, alts, info["alleles"])
            else:
                indel = gnomad_indel_vcf(rs)  # VCF-normalized, rsID-confirmed
                if indel:
                    chrom, pos, ref, alt = indel
                    how = "gnomAD-indel"

            if not alt:
                rec["status"] = ("skipped (no alt allele)" if place
                                 else "skipped (indel: no rsID-confirmed gnomAD VCF)")
            else:
                v = genome.Variant(chromosome=f"chr{chrom}", position=pos,
                                   reference_bases=ref, alternate_bases=alt)
                interval = v.reference_interval.resize(dna_client.SEQUENCE_LENGTH_1MB)
                df = None
                for attempt in range(3):
                    try:
                        s = MODEL.score_variant(interval=interval, variant=v, variant_scorers=SCORERS)
                        df = variant_scorers.tidy_scores(s)
                        break
                    except Exception as e:  # noqa: BLE001
                        if attempt == 2:
                            raise
                        time.sleep(5 * (attempt + 1))
                rec["scored_variant"] = f"chr{chrom}:{pos}:{ref}>{alt}"
                rec["alt_choice"] = how
                rec.update(summarize(df, rec["genes"]))
                rec["status"] = "ok"
        except Exception as e:  # noqa: BLE001
            rec["status"] = f"error: {type(e).__name__}: {str(e)[:120]}"
        results.append(rec)
        if i % 5 == 0 or i == len(todo):
            OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
            ok = sum(1 for r in results if r.get("status") == "ok")
            print(f"[{i}/{len(todo)}] {rs} -> {rec.get('status')}  (saved; {ok} ok total)", flush=True)
        time.sleep(0.3)

    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    ok = [r for r in results if r.get("status") == "ok"]
    ranked = sorted(ok, key=lambda r: r.get("max_expr_raw", 0), reverse=True)
    print(f"\nDONE. {len(results)} variants -> {OUT}  ({len(ok)} ok)")
    print("Top 10 by predicted expression effect size (max_expr_raw):")
    for r in ranked[:10]:
        te = r.get("top_expr") or {}
        print(f"  {r['rsid']:12} raw={r.get('max_expr_raw')}  {te.get('gene')} in {te.get('tissue')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
