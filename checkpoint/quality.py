"""Data-quality report and curator flags for an open CCDI molecular release.

The report lists the properties of the data that mislead an automated analyst.
Curator flags are suggestions for human review, never diagnoses.
"""
import collections
import csv
import os

# Diagnosis labels that carry no specific tumor type.
def is_nonspecific(dx):
    d = dx.lower()
    return d in {"missing", "unknown", "not reported"} or d.startswith("neoplasm")


# Entities whose defining alteration is a gene fusion, copy-number change or deletion and is
# therefore not visible in a somatic point-mutation (MAF) file. Sources: WHO Classification of
# Tumours, CNS 5th ed. (2021) and Soft Tissue and Bone 5th ed. (2020). To be reviewed clinically.
MAF_BLIND = {
    "Pilocytic astrocytoma": "KIAA1549::BRAF fusion (tandem duplication)",
    "Alveolar rhabdomyosarcoma": "PAX3::FOXO1 or PAX7::FOXO1 fusion",
    "Ewing sarcoma": "EWSR1::FLI1 and related fusions",
    "Atypical teratoid/rhabdoid tumor": "SMARCB1 loss, often by deletion",
    "Neuroblastoma, NOS": "MYCN amplification and segmental copy-number change",
    "Ependymoma, NOS": "ZFTA or YAP1 fusions; posterior fossa groups defined by methylation",
    "Synovial sarcoma, NOS": "SS18::SSX fusion",
    "Infantile fibrosarcoma": "ETV6::NTRK3 fusion",
    "Desmoplastic small round cell tumor": "EWSR1::WT1 fusion",
    "Alveolar soft part sarcoma": "ASPSCR1::TFE3 fusion",
}

# Protein changes that are characteristic of a specific entity. A case with a non-specific label
# that carries one of these is flagged for curator review. (gene, prefix of protein change)
CHARACTERISTIC = [
    ("H3-3A", "p.K28M", "Diffuse midline glioma, H3 K27-altered"),
    ("H3C2", "p.K28M", "Diffuse midline glioma, H3 K27-altered"),
    ("H3C3", "p.K28M", "Diffuse midline glioma, H3 K27-altered"),
    ("H3-3A", "p.G35", "Diffuse hemispheric glioma, H3 G34-mutant"),
    ("IDH1", "p.R132", "IDH-mutant glioma"),
    ("BRAF", "p.V600E", "BRAF V600E-altered tumor (several entities)"),
    ("BRAF", "p.V640E", "BRAF V600E-altered tumor (several entities)"),  # V600E under this file's transcript numbering
    ("CTNNB1", "p.S33", "WNT-pathway activated tumor"),
    ("CTNNB1", "p.D32", "WNT-pathway activated tumor"),
    ("CTNNB1", "p.G34", "WNT-pathway activated tumor"),
    ("CTNNB1", "p.S37", "WNT-pathway activated tumor"),
    ("MYOD1", "p.L122R", "Spindle cell/sclerosing rhabdomyosarcoma, MYOD1-mutant"),
    ("ACVR1", "p.G328", "Diffuse midline glioma (ACVR1 co-mutation)"),
]


# Genes with genuine recurrent hotspots, excluded when listing suspicious recurrent variants.
HOTSPOT_GENES = {"H3-3A", "H3C2", "H3C3", "BRAF", "CTNNB1", "IDH1", "IDH2", "TP53", "PIK3CA", "NRAS", "KRAS",
                 "HRAS", "FGFR1", "FGFR4", "MYOD1", "ACVR1", "DICER1", "PTPN11", "KBTBD4", "MYCN", "ALK",
                 "PPM1D", "PDGFRA", "MAX", "SMARCB1", "DDX3X", "AKT1", "EZH2", "SF3B1", "GNAS", "SMO"}


def recurrent_suspects(cases, changes, min_cases=20, min_labels=10):
    """Identical protein changes seen in many cases across many unrelated diagnosis labels, outside
    known hotspot genes. A true somatic hotspot tracks tumor type; these do not, which is the
    signature of a recurrent calling artifact or of germline variants left in a somatic file.
    First raised by the AI agents in their audit notes."""
    ids = [c for c in cases if not int(cases[c]["hypermutated"])]
    n = collections.Counter(v for c in ids for v in changes[c])
    out = []
    for (gene, change), k in n.most_common():
        if k < min_cases:
            break
        if gene in HOTSPOT_GENES:
            continue
        labels = {cases[c]["diagnosis"] for c in ids if (gene, change) in changes[c]}
        if len(labels) >= min_labels:
            out.append({"gene": gene, "protein_change": change, "cases": k, "diagnosis_labels": len(labels)})
    return out


def report(cases, genes, changes):
    n = len(cases)
    dx_counts = collections.Counter(c["diagnosis"] for c in cases.values())
    nonspecific = {d: k for d, k in dx_counts.items() if is_nonspecific(d)}
    nos = {d: k for d, k in dx_counts.items() if d.endswith(", NOS") and not is_nonspecific(d)}
    vital_missing = sum(1 for c in cases.values() if c["vital_status"].lower() in {"", "not reported", "unknown"})
    hyper = sorted(((int(c["n_nonsyn"]), cid) for cid, c in cases.items() if int(c["hypermutated"])), reverse=True)
    burdens = sorted(int(c["n_nonsyn"]) for c in cases.values())
    blind = {d: (dx_counts.get(d, 0), why) for d, why in MAF_BLIND.items() if dx_counts.get(d, 0)}
    flags = []
    for cid, c in cases.items():
        if not is_nonspecific(c["diagnosis"]):
            continue
        for gene, change in sorted(changes[cid]):
            for g, prefix, suggestion in CHARACTERISTIC:
                if gene == g and change.startswith(prefix):
                    flags.append({"case_id": cid, "current_label": c["diagnosis"], "site": c["site"],
                                  "finding": f"{gene} {change}", "suggested_review": suggestion})
    naming = {
        "BRAF p.V600E": sum(1 for c in cases if ("BRAF", "p.V600E") in changes[c]),
        "BRAF p.V640E": sum(1 for c in cases if ("BRAF", "p.V640E") in changes[c]),
        "H3-3A p.K27M": sum(1 for c in cases if ("H3-3A", "p.K27M") in changes[c]),
        "H3-3A p.K28M": sum(1 for c in cases if ("H3-3A", "p.K28M") in changes[c]),
    }
    return {
        "recurrent_suspects": recurrent_suspects(cases, changes),
        "naming": naming,
        "n_cases": n,
        "n_distinct_diagnoses": len(dx_counts),
        "nonspecific_labels": nonspecific,
        "n_nonspecific": sum(nonspecific.values()),
        "n_nos_suffix": sum(nos.values()),
        "vital_status_missing": vital_missing,
        "hypermutated": [{"case_id": cid, "n_nonsyn": k, "diagnosis": cases[cid]["diagnosis"]} for k, cid in hyper],
        "median_nonsyn": burdens[len(burdens) // 2],
        "zero_mutation_cases": sum(1 for b in burdens if b == 0),
        "maf_blind": blind,
        "n_maf_blind_cases": sum(k for k, _ in blind.values()),
        "curator_flags": flags,
    }


def write(rep, out_dir, release_label):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "curator_flags.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["case_id", "current_label", "site", "finding", "suggested_review"])
        w.writeheader()
        w.writerows(rep["curator_flags"])
    n = rep["n_cases"]
    pct = lambda k: f"{k} ({100 * k / n:.1f}%)"
    L = [f"# Data-quality report: {release_label}", "",
         f"Cases with an open somatic mutation file analyzed: **{n}**, across {rep['n_distinct_diagnoses']} distinct diagnosis labels.", "",
         "## What will mislead an automated analyst", "",
         "| Issue | Cases | Why it matters |", "|---|---|---|",
         f"| No specific diagnosis (missing, unknown, or 'Neoplasm ...') | {pct(rep['n_nonspecific'])} | These cases dilute every 'this diagnosis versus the rest' comparison |",
         f"| Diagnosis ends in 'NOS' | {pct(rep['n_nos_suffix'])} | Molecular subtypes are pooled, which hides subtype-specific signals |",
         f"| Vital status not reported | {pct(rep['vital_status_missing'])} | Survival claims cannot be tested in the open tier |",
         f"| Hypermutated tumors (more than 500 non-synonymous mutations) | {pct(len(rep['hypermutated']))} | A single such case can make hundreds of genes look enriched in a small group |",
         f"| Tumor types whose defining alteration is not a point mutation | {pct(rep['n_maf_blind_cases'])} | A mutation-only analysis reports 'no driver found' for these tumors |",
         f"| Cases with no non-synonymous mutation | {pct(rep['zero_mutation_cases'])} | Expected in pediatric tumors; not a data error |", "",
         "## Non-specific labels", "", "| Label | Cases |", "|---|---|"]
    L += [f"| {d} | {k} |" for d, k in sorted(rep["nonspecific_labels"].items(), key=lambda x: -x[1])]
    L += ["", "## Tumor types a mutation file cannot explain", "", "| Diagnosis | Cases | Defining alteration |", "|---|---|---|"]
    L += [f"| {d} | {k} | {why} |" for d, (k, why) in sorted(rep["maf_blind"].items(), key=lambda x: -x[1][0])]
    # summarized by diagnosis; individual cases are not listed in the published report
    hyp = collections.Counter(h["diagnosis"] for h in rep["hypermutated"])
    counts = sorted(h["n_nonsyn"] for h in rep["hypermutated"])
    L += ["", "## Hypermutated cases", "",
          f"{len(counts)} cases carry more than 500 non-synonymous mutations each "
          f"(range {counts[0]:,} to {counts[-1]:,}).", "", "| Diagnosis | Hypermutated cases |", "|---|---|"]
    L += [f"| {d} | {k} |" for d, k in sorted(hyp.items(), key=lambda x: (-x[1], x[0]))]
    nm = rep["naming"]
    L += ["", "## Residue numbering that defeats a text search", "",
          "| Mutation as clinicians name it | Cases found under that name | Name used in these files | Cases |", "|---|---|---|---|",
          f"| BRAF V600E | {nm['BRAF p.V600E']} | BRAF p.V640E | {nm['BRAF p.V640E']} |",
          f"| H3 K27M (H3-3A) | {nm['H3-3A p.K27M']} | H3-3A p.K28M | {nm['H3-3A p.K28M']} |", "",
          "BRAF is numbered on the annotation transcript, which is 40 residues longer than the one the clinical name refers to. "
          "The histone change follows standard notation, which counts the initial methionine; the clinical name does not. "
          "An analyst who searches for either clinical name finds nothing."]
    rs = rep["recurrent_suspects"]
    L += ["", "## Identical variants recurring across unrelated tumor types", "",
          "These identical protein changes appear in at least 20 cases spread over at least 10 diagnosis labels, in genes "
          "with no known hotspot. A real somatic hotspot tracks tumor type. A change that recurs regardless of tumor type "
          "is more likely a recurrent calling artifact or a germline variant left in the somatic file. "
          "**This issue was first raised by the AI agents in their audit notes, not by the authors.** "
          "It is offered for review by the Genomic Data Commons and CCDI, and has not been confirmed.", "",
          "| Gene | Protein change | Cases | Diagnosis labels |", "|---|---|---|---|"]
    L += [f"| {r['gene']} | {r['protein_change']} | {r['cases']} | {r['diagnosis_labels']} |" for r in rs]
    L += ["", f"Together these {len(rs)} variants account for {sum(r['cases'] for r in rs)} case-level calls. "
          "An enrichment analysis that does not remove them will report these genes as findings in whichever small "
          "group happens to carry a few."]
    by = collections.Counter(f["suggested_review"] for f in rep["curator_flags"])
    L += ["", "## Flags for curator review", "",
          f"{len({f['case_id'] for f in rep['curator_flags']})} cases carry a non-specific label and a mutation that is characteristic of a specific entity. "
          "These are suggestions for review by CCDI curators and pathologists. They are not diagnoses. The full list is written to `curator_flags.csv` when the report is run locally; it is not published in this repository.", "",
          "| Suggested review category | Flags |", "|---|---|"]
    L += [f"| {s} | {k} |" for s, k in by.most_common()]
    with open(os.path.join(out_dir, "data_quality_report.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
