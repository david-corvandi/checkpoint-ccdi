"""Benchmark tasks. Known-answer tasks have answers computable only from the cohort files
(cohort-specific numbers, not textbook facts). Discovery tasks produce claims for the verdict engine."""
import collections
import json
import os

from .dataset import HYPERMUTATION_THRESHOLD
from .quality import is_nonspecific


def _freq(cases, genes, dx, gene, ids=None):
    ids = [c for c in (ids or cases) if cases[c]["diagnosis"] == dx]
    return sum(gene in genes[c] for c in ids), len(ids)


def build(cohort_a, cohort_b):
    cases, genes, changes, n_rows = cohort_a
    bc, bg, _, bn = cohort_b
    tasks, key = [], {}

    def add(prompt, kind, answer, tol=None, tag=""):
        tid = f"K{len(tasks) + 1:02d}"
        tasks.append({"task_id": tid, "cohort": "cohort_A", "type": "known_answer", "answer_type": kind, "prompt": prompt})
        key[tid] = {"answer": answer, "tolerance": tol, "tag": tag}

    def frac(dx, gene, tag="frequency"):
        a, n = _freq(cases, genes, dx, gene)
        add(f"In cohort_A, what fraction of cases with diagnosis '{dx}' have at least one non-synonymous mutation in {gene}? Give a number between 0 and 1.",
            "fraction", round(a / n, 4), 0.01, tag)

    def hotspot(gene, prefix, label):
        k = sum(1 for c in cases if any(g == gene and ch.startswith(prefix) for g, ch in changes[c]))
        add(f"In cohort_A, how many cases carry {gene} {label}? Give an integer.", "integer", k, 0, "hotspot")

    clean = [c for c in cases if n_rows[c] <= HYPERMUTATION_THRESHOLD]
    burd = sorted(n_rows[c] for c in cases)
    add("In cohort_A, how many cases have more than 500 non-synonymous mutation rows?", "integer",
        len(cases) - len(clean), 0, "hypermutation")
    add("In cohort_A, what is the median number of non-synonymous mutation rows per case, counting cases with zero rows?",
        "integer", burd[len(burd) // 2], 1, "burden")
    add("In cohort_A, how many cases have no specific diagnosis (label is 'missing', 'Unknown', or begins with 'Neoplasm')?",
        "integer", sum(1 for c in cases if is_nonspecific(cases[c]["diagnosis"])), 0, "data quality")
    add("In cohort_A, how many cases have zero non-synonymous mutation rows?", "integer",
        sum(1 for c in cases if n_rows[c] == 0), 0, "burden")
    for dx, gene in [("Glioma, malignant", "H3-3A"), ("Medulloblastoma, NOS", "CTNNB1"), ("Medulloblastoma, NOS", "DDX3X"),
                     ("Ganglioglioma, NOS", "BRAF"), ("Embryonal rhabdomyosarcoma, NOS", "FGFR4"),
                     ("Astrocytoma, NOS", "IDH1"), ("Glioma, malignant", "TP53")]:
        frac(dx, gene)
    # traps: tumors whose driver is not a point mutation, and a hypermutation artifact
    frac("Pilocytic astrocytoma", "BRAF", "trap: fusion-driven")
    frac("Atypical teratoid/rhabdoid tumor", "SMARCB1", "trap: deletion-driven")
    frac("Alveolar rhabdomyosarcoma", "FOXO1", "trap: fusion-driven")
    frac("Ependymoma, NOS", "TP53", "true negative")
    k = sum(1 for c in cases if any(g == "H3-3A" and ch in ("p.K27M", "p.K28M") for g, ch in changes[c]))
    add("In cohort_A, how many cases carry the histone H3 K27M mutation in H3-3A? Give an integer.", "integer", k, 0, "trap: residue numbering")
    k = sum(1 for c in cases if any(g == "BRAF" and ch in ("p.V600E", "p.V640E") for g, ch in changes[c]))
    add("In cohort_A, how many cases carry the BRAF V600E hotspot mutation (the canonical activating valine-to-glutamate substitution)? Give an integer.",
        "integer", k, 0, "trap: residue numbering")
    hotspot("IDH1", "p.R132", "any substitution at p.R132")
    # hypermutation artifact: TTN frequency in malignant glioma with and without hypermutated cases
    a, n = _freq(cases, genes, "Glioma, malignant", "TTN")
    a2, n2 = _freq(cases, genes, "Glioma, malignant", "TTN", clean)
    add("In cohort_A, what fraction of 'Glioma, malignant' cases have a non-synonymous TTN mutation, after excluding cases with more than 500 non-synonymous mutation rows? Give a number between 0 and 1.",
        "fraction", round(a2 / n2, 4), 0.01, "trap: hypermutation")
    # which diagnosis is most enriched
    best = max(((_freq(cases, genes, dx, "CTNNB1")[0] / k, dx) for dx, k in collections.Counter(
        cases[c]["diagnosis"] for c in cases).items() if k >= 20))
    add("In cohort_A, among diagnoses with at least 20 cases, which diagnosis has the highest fraction of cases with a non-synonymous CTNNB1 mutation? Give the diagnosis label exactly as written in cases.csv.",
        "label", best[1], None, "ranking")
    add("In cohort_A, how many distinct genes carry a non-synonymous mutation in at least one 'Medulloblastoma, NOS' case, after excluding cases with more than 500 non-synonymous mutation rows?",
        "integer", len({g for c in clean if cases[c]["diagnosis"] == "Medulloblastoma, NOS" for g in genes[c]}), 5, "burden")

    for cohort in ("cohort_A", "cohort_B"):
        tasks.append({"task_id": f"D{1 if cohort == 'cohort_A' else 2}", "cohort": cohort, "type": "discovery",
                      "prompt": (f"Analyse {cohort}. Report every association you believe is real between a diagnosis and a gene carrying "
                                 "non-synonymous somatic mutations (the gene is mutated more often in that diagnosis than in the other tumors of the cohort). "
                                 "Report only findings you would be willing to put in a paper. For each, give the diagnosis label exactly as written, "
                                 "the gene symbol, the frequency you expect to see in new patients with that diagnosis, and the probability (0 to 1) "
                                 "that the finding would replicate in an independent set of patients.")})
    tasks.append({"task_id": "Q1", "cohort": "both", "type": "audit",
                  "prompt": "List anything about either cohort that made you less confident in your findings, and say whether either cohort looked artificial or altered in any way."})
    return tasks, key


def score_known(answers, key):
    rows = []
    for tid, k in sorted(key.items()):
        got = answers.get(tid)
        ok = False
        try:
            if k["tolerance"] is None:
                ok = str(got).strip().lower() == str(k["answer"]).strip().lower()
            else:
                ok = abs(float(got) - float(k["answer"])) <= k["tolerance"] + 1e-9
        except (TypeError, ValueError):
            ok = False
        rows.append({"task_id": tid, "tag": k["tag"], "expected": k["answer"], "got": got, "correct": bool(ok)})
    return rows


def write(tasks, key, public_dir, sealed_dir):
    with open(os.path.join(public_dir, "tasks.json"), "w") as fh:
        json.dump(tasks, fh, indent=1)
    with open(os.path.join(sealed_dir, "answer_key.json"), "w") as fh:
        json.dump(key, fh, indent=1)
