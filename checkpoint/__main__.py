"""Command line: python -m checkpoint <command>"""
import argparse
import json
import os

from . import baselines, checksums, controls, dataset, gdc, power, quality, score, tasks

RELEASE = "CCDI-MCI open somatic mutations, GDC Data Release 46 (10 Aug 2026)"


def main():
    ap = argparse.ArgumentParser(prog="checkpoint", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download the open CCDI-MCI mutation files that benchmark v0.1 was frozen on")
    f.add_argument("--all", action="store_true", help="fetch every open file in the project, not only the v0.1 list")
    sub.add_parser("verify", help="check that the rebuilt data matches the published checksums")
    sub.add_parser("build", help="build the analysis-ready tables")
    sub.add_parser("report", help="write the data-quality report, curator flags and power map")
    sub.add_parser("bench", help="build benchmark cohorts, planted controls, tasks and answer key")
    sub.add_parser("baselines", help="score the two scripted reference analysts")
    s = sub.add_parser("score", help="score a submission.json")
    s.add_argument("submission")
    s.add_argument("--out")
    a = ap.parse_args()
    bench = "benchmark/v0.1"
    if a.cmd == "fetch":
        ids = None
        if not a.all:
            with open(f"{bench}/gdc_file_ids.txt") as fh:
                ids = [line.strip() for line in fh if line.strip()]
        print(gdc.fetch("CCDI-MCI", "data/raw/CCDI-MCI", only_ids=ids))
    elif a.cmd == "verify":
        bad = checksums.verify(f"{bench}/checksums.json")
        print("all files match the published checksums" if not bad else "MISMATCH: " + ", ".join(bad))
        raise SystemExit(1 if bad else 0)
    elif a.cmd == "build":
        dataset.build("data/raw/CCDI-MCI", "package")
    elif a.cmd == "report":
        c, g, ch = dataset.load("package")
        out = "results/release_2026-08"
        quality.write(quality.report(c, g, ch), out, RELEASE)
        # NCI reports more than 10,000 participants enrolled in MCI (program page, updated 13 July 2026);
        # the GDC project CCDI-MCI lists 3,076 cases.
        power.write(power.build(c, 10000, 3076), out, RELEASE,
                    "if 10,000 enrolled participants were released with the same mix of diagnoses (an assumption)")
        print("wrote", out)
    elif a.cmd == "bench":
        n, planted, spiked, spiked_s = controls.build("package", f"{bench}/public", f"{bench}/sealed")
        t, key = tasks.build(controls.load_cohort(f"{bench}/public/cohort_A"), controls.load_cohort(f"{bench}/public/cohort_B"))
        tasks.write(t, key, f"{bench}/public", f"{bench}/sealed")
        print(n, len(t), "tasks")
    elif a.cmd == "baselines":
        b = score.load_bench(bench)
        os.makedirs("results/agents", exist_ok=True)
        for name, fn in (("reference-uncorrected", baselines.uncorrected), ("reference-corrected", baselines.corrected)):
            subm = {"agent": name, "answers": {}, "claims_cohort_A": fn(b["A"]), "claims_cohort_B": fn(b["B"])}
            for budget, tag in ((10 ** 9, "all-claims"), (None, "budget")):
                res = score.score_submission(subm, b) if budget is None else score.score_submission(subm, b, budget)
                res["agent"] = name
                with open(f"results/agents/{name}.{tag}.json", "w") as fh:
                    json.dump(res, fh, indent=1)
                print(name, tag, json.dumps(res["summary"]))
    elif a.cmd == "score":
        out = a.out or os.path.join(os.path.dirname(a.submission), "scored.json")
        print(json.dumps(score.score_file(a.submission, bench, out)["summary"], indent=1))


if __name__ == "__main__":
    main()
