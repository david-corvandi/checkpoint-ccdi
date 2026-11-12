"""Power map: for each diagnosis, what can and cannot be concluded from the cases released so far."""
import collections
import csv
import os

from . import stats
from .quality import is_nonspecific

BACKGROUND = 0.02      # reference background frequency of a gene in other tumors
EFFECT = 0.15          # reference effect: gene mutated in 15% of the diagnosis
ALPHA_SINGLE = 0.05    # one claim tested alone
ALPHA_STREAM = 0.0005  # a claim tested inside a long stream under online error control


def tier(n):
    p = stats.power_binomial(n, EFFECT, BACKGROUND, ALPHA_STREAM)
    if p >= 0.8:
        return "testable"
    if stats.power_binomial(n, EFFECT, BACKGROUND, ALPHA_SINGLE) >= 0.8:
        return "testable only as a single pre-specified claim"
    return "not yet testable"


def build(cases, enrolled_total=None, released_total=None):
    counts = collections.Counter(c["diagnosis"] for c in cases.values()
                                 if not is_nonspecific(c["diagnosis"]) and not int(c["hypermutated"]))
    scale = (enrolled_total / released_total) if enrolled_total and released_total else None
    rows = []
    for dx, n in counts.most_common():
        row = {"diagnosis": dx, "cases": n,
               "power_single_claim": round(stats.power_binomial(n, EFFECT, BACKGROUND, ALPHA_SINGLE), 2),
               "power_in_stream": round(stats.power_binomial(n, EFFECT, BACKGROUND, ALPHA_STREAM), 2),
               "smallest_detectable_frequency": stats.min_detectable(n, BACKGROUND, ALPHA_STREAM) or "",
               "status": tier(n)}
        if scale:
            proj = round(n * scale)
            row["projected_cases_at_full_enrollment"] = proj
            row["projected_status"] = tier(proj)
        rows.append(row)
    return rows


def write(rows, out_dir, release_label, note=""):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "power_map.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by = collections.Counter(r["status"] for r in rows)
    cases_by = collections.Counter()
    for r in rows:
        cases_by[r["status"]] += r["cases"]
    L = [f"# Power map: {release_label}", "",
         f"Reference claim: a gene mutated in {int(EFFECT * 100)}% of a diagnosis against a {int(BACKGROUND * 100)}% background. "
         f"'Testable' means at least 80% power at a per-claim level of {ALPHA_STREAM}, the level a claim realistically faces inside a long stream of claims. "
         "Cases with a non-specific diagnosis and hypermutated cases are excluded.", "",
         "| Status | Diagnoses | Cases |", "|---|---|---|"]
    for s in ["testable", "testable only as a single pre-specified claim", "not yet testable"]:
        L.append(f"| {s} | {by[s]} | {cases_by[s]} |")
    if "projected_status" in rows[0]:
        pb = collections.Counter(r["projected_status"] for r in rows)
        L += ["", f"Projection {note}:", "", "| Status at full enrollment | Diagnoses |", "|---|---|"]
        L += [f"| {s} | {pb[s]} |" for s in ["testable", "testable only as a single pre-specified claim", "not yet testable"]]
    L += ["", "## Diagnoses with at least 20 cases", "",
          "| Diagnosis | Cases | Power, single claim | Power, in stream | Smallest detectable frequency | Status |", "|---|---|---|---|---|---|"]
    for r in rows:
        if r["cases"] >= 20:
            L.append(f"| {r['diagnosis']} | {r['cases']} | {r['power_single_claim']} | {r['power_in_stream']} | {r['smallest_detectable_frequency']} | {r['status']} |")
    L += ["", f"The remaining {sum(1 for r in rows if r['cases'] < 20)} diagnoses have fewer than 20 cases each "
          f"({sum(r['cases'] for r in rows if r['cases'] < 20)} cases in total). Full table: `power_map.csv`."]
    with open(os.path.join(out_dir, "power_map.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
