#!/usr/bin/env python3
"""Validate curated health_variants.json against live public reference databases.

BUILD/CURATION-TIME ONLY. This script queries PUBLIC reference variants (by rsID)
against ClinVar, gnomAD and dbSNP via the Google DeepMind science-skills wrapper
scripts. It never touches user genotype data and is not imported by the Flask app.
It is read-only with respect to the curated data: it writes a diff report and a
list of *proposed* corrections for human review; it does not edit health_variants.json.

gnomAD lookups are ALLELE-PINNED for SNVs: we resolve the GRCh38 ref/alt via dbSNP,
match the curated risk_allele (trying the reverse-complement for minus-strand reports),
and query gnomAD by chrom-pos-ref-alt. This avoids the multi-allelic mismatch that a
bare by-rsID lookup produces (e.g. GSTP1 rs1695 picking the rare A>T instead of A>G).

Usage:
    python scripts/validate_health_variants.py [--limit N] [--skills-dir PATH]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CURATED = REPO / "data" / "curated" / "health_variants.json"
OUT_DIR = REPO / "data" / "validation"
TMP = OUT_DIR / "_tmp"

FREQ_FOLD_TOLERANCE = 5.0   # fold a curated freq may differ from gnomAD before flagging
NCBI_SLEEP = 0.45           # polite pacing for NCBI (dbSNP + ClinVar), 3 req/s w/o key
_COMP = {"A": "T", "T": "A", "C": "G", "G": "C"}


def run_skill(skill_dir: Path, script_args: list[str], out_path: Path, timeout: int = 120):
    """Run a science-skill wrapper script via `uv run`; return (parsed_json, error)."""
    cmd = ["uv", "run", *script_args, "--output", str(out_path)]
    try:
        r = subprocess.run(cmd, cwd=skill_dir, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if r.returncode != 0:
        return None, (r.stderr or r.stdout or "nonzero exit").strip().splitlines()[-1][:200]
    try:
        return json.loads(out_path.read_text()), None
    except Exception as e:  # noqa: BLE001
        return None, f"parse error: {e}"


def seq_id_to_chrom(seq_id: str):
    """NC_000011.10 -> '11'; NC_000023.* -> 'X'; NC_000024.* -> 'Y'."""
    if not seq_id or not seq_id.startswith("NC_"):
        return None
    try:
        n = int(seq_id.split(".")[0].replace("NC_", ""))
    except ValueError:
        return None
    return {23: "X", 24: "Y"}.get(n, str(n))


def parse_snv_placement(dbsnp: dict):
    """For an SNV, return (chrom, vcf_pos, ref, [alts]) on GRCh38, else None."""
    if (dbsnp.get("variant_type") or "") != "snv":
        return None
    for p in dbsnp.get("placements") or []:
        chrom = seq_id_to_chrom(p.get("seq_id", ""))
        if not chrom:
            continue
        alleles = p.get("alleles") or []
        ref = next((a.get("deleted_sequence") for a in alleles if a.get("deleted_sequence")), None)
        spdi_pos = next((a.get("position") for a in alleles if a.get("position") is not None), None)
        alts = [a.get("inserted_sequence") for a in alleles
                if a.get("is_variant") and a.get("inserted_sequence") != a.get("deleted_sequence")]
        if ref and spdi_pos is not None and alts:
            return chrom, spdi_pos + 1, ref, alts  # SPDI is 0-based -> VCF 1-based
    return None


def gnomad_global_af(payload: dict):
    """Extract (global_af, popmax_faf95, popmax_pop, variant_id) from gnomAD output."""
    v = (payload or {}).get("data", {}).get("variant")
    if not v:
        return None, None, None, None
    joint = v.get("joint") or {}
    ac, an = joint.get("ac"), joint.get("an")
    global_af = (ac / an) if ac and an else None
    if global_af is None:
        for src in ("exome", "genome"):
            af = (v.get(src) or {}).get("af")
            if af is not None:
                global_af = af
                break
    faf = joint.get("faf95") or {}
    return global_af, faf.get("popmax"), faf.get("popmax_population"), v.get("variant_id")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skills-dir", default=str(Path.home() / "science-skills" / "skills"))
    args = ap.parse_args()

    skills = Path(args.skills_dir)
    dbsnp_dir = skills / "dbsnp_database"
    clinvar_dir = skills / "clinvar_database"
    gnomad_dir = skills / "gnomad_database"
    TMP.mkdir(parents=True, exist_ok=True)

    entries = json.loads(CURATED.read_text())
    if args.limit:
        entries = entries[: args.limit]

    results = []
    total = len(entries)
    for i, e in enumerate(entries, 1):
        rsid = (e.get("rsid") or "").strip()
        rec = {
            "rsid": rsid, "gene": e.get("gene"),
            "curated_significance": (e.get("significance") or "").strip(),
            "curated_frequency": e.get("population_frequency"),
            "risk_allele": e.get("risk_allele"),
            "variant_name": e.get("variant_name"), "errors": [],
        }
        print(f"[{i}/{total}] {rsid} ({e.get('gene')})", flush=True)
        if not rsid.startswith("rs"):
            rec["errors"].append("no usable rsID")
            results.append(rec)
            continue

        # --- dbSNP: gene / type / GRCh38 ref+alts ---
        dbsnp, err = run_skill(dbsnp_dir, ["scripts/dbsnp_cli.py", "get-variant", rsid], TMP / "dbsnp.json")
        snv = None
        if err:
            rec["errors"].append(f"dbsnp: {err}")
        else:
            rec["dbsnp_genes"] = dbsnp.get("genes")
            rec["dbsnp_variant_type"] = dbsnp.get("variant_type")
            snv = parse_snv_placement(dbsnp)
            if snv:
                rec["grch38"] = f"{snv[0]}:{snv[1]} {snv[2]}>{','.join(snv[3])}"
        time.sleep(NCBI_SLEEP)

        # --- ClinVar: current classification + review status (xref) ---
        cvs, err = run_skill(clinvar_dir, ["scripts/clinvar_api.py", "search", "--query", rsid, "--retmax", "5"], TMP / "cv_search.json")
        if err:
            rec["errors"].append(f"clinvar search: {err}")
        else:
            vids = cvs.get("variant_ids") or []
            rec["clinvar_match_count"] = len(vids)
            if vids:
                time.sleep(NCBI_SLEEP)
                summ, err2 = run_skill(clinvar_dir, ["scripts/clinvar_api.py", "summary", "--variant_ids", vids[0]], TMP / "cv_sum.json")
                if err2:
                    rec["errors"].append(f"clinvar summary: {err2}")
                elif summ:
                    s0 = summ[0]
                    rec["clinvar_significance"] = s0.get("clinical_significance")
                    rec["clinvar_review_status"] = s0.get("review_status")
                    rec["clinvar_last_evaluated"] = s0.get("last_evaluated")
        time.sleep(NCBI_SLEEP)

        # --- gnomAD: allele-pinned + rsID-CONFIRMED (handles minus-strand multi-allelic) ---
        # For an SNV we build chrom-pos-ref-alt for the curated risk allele AND its
        # complement, then accept only the candidate whose gnomAD record carries our
        # rsID. This defeats the trap where a literal coding allele also exists as a
        # rare genomic alt (e.g. SERPINA1 C>A vs the real minus-strand C>T).
        gn = None
        method = None
        confirmed = False

        def _query_vid(vid):
            p, _e = run_skill(gnomad_dir, ["scripts/get_variant_frequency.py", "--variant_id", vid], TMP / "gnomad.json")
            v = ((p or {}).get("data", {}) or {}).get("variant") or {}
            return p, (v.get("rsids") or [])

        if snv:
            chrom, pos, ref, alts = snv
            ra = (rec.get("risk_allele") or "").strip().upper()
            comp = _COMP.get(ra)
            candidates = []
            if ra in alts:
                candidates.append((ra, "direct"))
            if comp and comp in alts and comp != ra:
                candidates.append((comp, "complement/minus-strand"))
            for a, kind in candidates:
                vid = f"{chrom}-{pos}-{ref}-{a}"
                p, rids = _query_vid(vid)
                if p is not None and rsid in rids:
                    gn, method, confirmed = p, f"allele-pinned ({kind})", True
                    rec["gnomad_query"] = vid
                    break
                time.sleep(0.2)

        if gn is None:  # indel, no candidate confirmed, or unmatched allele
            p, e = run_skill(gnomad_dir, ["scripts/get_variant_frequency.py", "--rsid", rsid], TMP / "gnomad.json")
            if e:
                rec["errors"].append(f"gnomad: {e}")
            else:
                gn = p
                v = ((p or {}).get("data", {}) or {}).get("variant") or {}
                confirmed = rsid in (v.get("rsids") or [])
                method = "by-rsid" + (" (rsID-confirmed)" if confirmed else " (UNCONFIRMED)")

        rec["gnomad_method"] = method
        rec["gnomad_confirmed"] = confirmed
        if gn is not None:
            g_af, popmax, popmax_pop, _vid = gnomad_global_af(gn)
            rec["gnomad_global_af"] = g_af
            rec["gnomad_popmax_faf95"] = popmax
            rec["gnomad_popmax_pop"] = popmax_pop
            if g_af is None:
                rec["gnomad_note"] = "not observed (consistent with very rare/pathogenic)"
        time.sleep(0.2)

        # --- verdicts ---
        cur_sig = rec["curated_significance"]
        live_sig = (rec.get("clinvar_significance") or "").strip()
        if live_sig:
            if cur_sig.lower() == live_sig.lower():
                rec["significance_verdict"] = "match"
            elif any(k in live_sig.lower() for k in ("benign",)) and any(k in cur_sig.lower() for k in ("pathogenic",)):
                rec["significance_verdict"] = f"CONFLICT: curated '{cur_sig}' vs ClinVar '{live_sig}'"
            else:
                rec["significance_verdict"] = f"differs: curated '{cur_sig}' vs ClinVar '{live_sig}'"
        else:
            rec["significance_verdict"] = "no ClinVar classification"

        cur_freq, g_af = rec["curated_frequency"], rec.get("gnomad_global_af")
        if isinstance(cur_freq, (int, float)) and cur_freq > 0 and isinstance(g_af, (int, float)) and g_af > 0:
            fold = max(cur_freq / g_af, g_af / cur_freq)
            rec["freq_fold_diff"] = round(fold, 1)
            base = "ok" if fold <= FREQ_FOLD_TOLERANCE else f"off by {fold:.0f}x"
            # Sanity guard: a confirmed-but-implausible AF usually means the curated
            # risk_allele is the reference base or otherwise malformed (e.g. ABCC11
            # rs17822931 risk_allele 'C'). Flag for human review; never auto-apply.
            rec["gnomad_af_suspect"] = bool(fold > 1000 and g_af < 1e-4 and cur_freq > 0.05)
            verdict = base if confirmed else base + " (UNCONFIRMED allele)"
            if rec["gnomad_af_suspect"]:
                verdict += " — IMPLAUSIBLE, review curated risk_allele"
            rec["freq_verdict"] = verdict
        elif g_af is None and isinstance(cur_freq, (int, float)):
            rec["freq_verdict"] = "gnomAD has no global AF (very rare); unverifiable here"
        else:
            rec["freq_verdict"] = "n/a"
        results.append(rec)

    # ---- outputs ----
    (OUT_DIR / "health_variants_validation.json").write_text(json.dumps(results, indent=2))

    # proposed frequency updates: trustworthy lookups only —
    #   SNVs: must be allele-pinned (guards against multi-allelic mismatch)
    #   indels: by-rsID accepted only if gnomAD returns the SAME rsID (identity check)
    proposals = []
    for r in results:
        if not (isinstance(r.get("gnomad_global_af"), (int, float))
                and isinstance(r.get("curated_frequency"), (int, float))
                and r.get("freq_fold_diff", 0) > FREQ_FOLD_TOLERANCE):
            continue
        if not r.get("gnomad_confirmed") or r.get("gnomad_af_suspect"):
            continue
        confidence = ("high (allele-pinned, rsID-confirmed)"
                      if str(r.get("gnomad_method", "")).startswith("allele-pinned")
                      else "medium (by-rsID, rsID-confirmed)")
        proposals.append({
            "rsid": r["rsid"], "gene": r["gene"],
            "old_population_frequency": r["curated_frequency"],
            "new_global_af": r["gnomad_global_af"],
            "popmax_faf95": r.get("gnomad_popmax_faf95"),
            "popmax_pop": r.get("gnomad_popmax_pop"),
            "fold_diff": r.get("freq_fold_diff"), "confidence": confidence,
        })
    (OUT_DIR / "proposed_frequency_updates.json").write_text(json.dumps(proposals, indent=2))

    conflicts = [r for r in results if str(r.get("significance_verdict", "")).startswith("CONFLICT")]
    freq_off = [r for r in results if str(r.get("freq_verdict", "")).startswith("off")]
    errored = [r for r in results if r.get("errors")]

    def table(rows):
        out = ["| rsid | gene | curated sig | ClinVar (review) | sig verdict | cur freq | gnomAD AF | method | freq verdict |",
               "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            af = r.get("gnomad_global_af")
            af_s = f"{af:.2e}" if isinstance(af, (int, float)) else (r.get("gnomad_note", "-") or "-")
            m = (r.get("gnomad_method") or "-").replace("allele-pinned", "pinned").replace(" (allele not pinned)", "")
            out.append(
                f"| {r['rsid']} | {r.get('gene','-')} | {r.get('curated_significance','-')} | "
                f"{r.get('clinvar_significance','-')} ({r.get('clinvar_review_status','')}) | "
                f"{r.get('significance_verdict','-')} | {r.get('curated_frequency','-')} | {af_s} | {m} | {r.get('freq_verdict','-')} |")
        return "\n".join(out)

    lines = ["# Health-variant reference validation (allele-pinned)\n",
             f"Validated **{len(results)}** curated variants against live ClinVar / gnomAD / dbSNP "
             "(GDM science-skills, build-time only). gnomAD SNV lookups are allele-pinned.\n",
             "## Summary\n",
             f"- Significance **conflicts** (curated pathogenic, ClinVar benign): **{len(conflicts)}**",
             f"- Frequency off by >{int(FREQ_FOLD_TOLERANCE)}x (allele-pinned only counted as solid): **{len(freq_off)}**",
             f"- Proposed (trustworthy) frequency updates: **{len(proposals)}**",
             f"- Retrieval errors: **{len(errored)}**\n",
             "## ⚠️ Significance conflicts\n", table(conflicts) + "\n",
             "## Frequency discrepancies\n", table(freq_off) + "\n",
             "## Full results\n", table(results) + "\n"]
    if errored:
        lines.append("## Retrieval errors\n")
        lines += [f"- {r['rsid']} ({r.get('gene')}): {'; '.join(r['errors'])}" for r in errored]
    (OUT_DIR / "health_variants_validation.md").write_text("\n".join(lines))

    print("\nDONE.")
    print("  report:    ", OUT_DIR / "health_variants_validation.md")
    print("  proposals: ", OUT_DIR / "proposed_frequency_updates.json", f"({len(proposals)} updates)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
