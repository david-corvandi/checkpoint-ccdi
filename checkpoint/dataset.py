"""Turn raw GDC MAF archives into the analysis-ready tables used everywhere else.

Outputs
  cases.csv      one row per case: diagnosis, age, sex, site, mutation burden, flags
  mutations.csv  one row per case x gene x protein change (non-synonymous only)
"""
import csv
import glob
import gzip
import json
import os
import tarfile

NONSYN = {"Missense_Mutation", "Nonsense_Mutation", "Frame_Shift_Del", "Frame_Shift_Ins",
          "In_Frame_Del", "In_Frame_Ins", "Splice_Site", "Translation_Start_Site", "Nonstop_Mutation"}
HYPERMUTATION_THRESHOLD = 500  # non-synonymous mutations in the exome; fixed rule, see docs/methods.md
UNINFORMATIVE = {"missing", "unknown", "not reported"}


def _first(lst):
    return (lst or [{}])[0]


def build(raw_dir, out_dir, log=print):
    with open(os.path.join(raw_dir, "manifest.json")) as fh:
        man = {h["file_id"]: h for h in json.load(fh)}
    cases, muts, files_seen = {}, {}, set()
    for tgz in sorted(glob.glob(os.path.join(raw_dir, "*.tar.gz"))):
        with tarfile.open(tgz) as tf:
            for m in tf:
                if not m.name.endswith(".maf.gz"):
                    continue
                fid = m.name.split("/")[0]
                if fid in files_seen or fid not in man:
                    continue
                files_seen.add(fid)
                c = man[fid]["cases"][0]
                cid = c["submitter_id"]
                dx = _first(c.get("diagnoses"))
                demo = c.get("demographic") or {}
                cases.setdefault(cid, {
                    "case_id": cid,
                    "diagnosis": (dx.get("primary_diagnosis") or "missing").strip(),
                    "morphology": dx.get("morphology") or "",
                    "site": dx.get("tissue_or_organ_of_origin") or "",
                    "age_days": dx.get("age_at_diagnosis") if dx.get("age_at_diagnosis") is not None else "",
                    "sex": demo.get("sex_at_birth") or "",
                    "vital_status": demo.get("vital_status") or "",
                })
                hdr = None
                for line in gzip.decompress(tf.extractfile(m).read()).decode("utf-8", "replace").splitlines():
                    if line.startswith("#"):
                        continue
                    f = line.split("\t")
                    if hdr is None:
                        hdr = {k: i for i, k in enumerate(f)}
                        continue
                    vc = f[hdr["Variant_Classification"]]
                    if vc in NONSYN:
                        muts.setdefault(cid, set()).add((f[hdr["Hugo_Symbol"]], vc, f[hdr["HGVSp_Short"]]))
    for cid, c in cases.items():
        genes = {g for g, _, _ in muts.get(cid, ())}
        c["n_nonsyn"] = len(muts.get(cid, ()))
        c["n_genes_mutated"] = len(genes)
        c["hypermutated"] = int(c["n_nonsyn"] > HYPERMUTATION_THRESHOLD)
        c["diagnosis_informative"] = int(c["diagnosis"].lower() not in UNINFORMATIVE)
    os.makedirs(out_dir, exist_ok=True)
    cols = ["case_id", "diagnosis", "morphology", "site", "age_days", "sex", "vital_status",
            "n_nonsyn", "n_genes_mutated", "hypermutated", "diagnosis_informative"]
    with open(os.path.join(out_dir, "cases.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for cid in sorted(cases):
            w.writerow(cases[cid])
    with gzip.open(os.path.join(out_dir, "mutations.csv.gz"), "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "gene", "variant_class", "protein_change"])
        for cid in sorted(muts):
            for row in sorted(muts[cid]):
                w.writerow([cid, *row])
    log(f"files parsed: {len(files_seen)} of {len(man)} in manifest; cases: {len(cases)}; "
        f"mutation rows: {sum(len(v) for v in muts.values())}")
    return len(files_seen), len(man), len(cases)


def load(pkg_dir):
    """Return (cases: dict case_id -> row dict, genes: dict case_id -> set of mutated genes, hotspots)."""
    with open(os.path.join(pkg_dir, "cases.csv")) as fh:
        cases = {r["case_id"]: r for r in csv.DictReader(fh)}
    genes = {c: set() for c in cases}
    changes = {c: set() for c in cases}
    with gzip.open(os.path.join(pkg_dir, "mutations.csv.gz"), "rt") as fh:
        for r in csv.DictReader(fh):
            genes[r["case_id"]].add(r["gene"])
            changes[r["case_id"]].add((r["gene"], r["protein_change"]))
    return cases, genes, changes
