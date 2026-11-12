"""Score one submission (an agent's answers and claims) against a benchmark version."""
import json
import os

from . import controls, tasks, verdict


def load_bench(bench_dir):
    pub, sealed = os.path.join(bench_dir, "public"), os.path.join(bench_dir, "sealed")
    with open(os.path.join(sealed, "answer_key.json")) as fh:
        key = json.load(fh)
    with open(os.path.join(sealed, "planted.json")) as fh:
        planted = json.load(fh)["planted_effects"]
    with open(os.path.join(sealed, "spiked.json")) as fh:
        spiked = json.load(fh)["planted_effects"]
    with open(os.path.join(sealed, "spiked_v2.json")) as fh:
        spiked_s = json.load(fh)["planted_effects"]
    with open(os.path.join(sealed, "spiked_v3.json")) as fh:
        spiked_t = json.load(fh)["planted_effects"]
    return {"T": controls.load_cohort(os.path.join(pub, "cohort_T")), "spiked_t": spiked_t,
            "S": controls.load_cohort(os.path.join(pub, "cohort_S")), "spiked_s": spiked_s,
            "C": controls.load_cohort(os.path.join(pub, "cohort_C")), "spiked": spiked,
            "A": controls.load_cohort(os.path.join(pub, "cohort_A")),
            "B": controls.load_cohort(os.path.join(pub, "cohort_B")),
            "H": controls.load_cohort(os.path.join(sealed, "held_back")),
            "key": key, "planted": planted}


def score_submission(sub, bench, budget=verdict.CLAIM_BUDGET):
    known = tasks.score_known(sub.get("answers", {}), bench["key"])
    rep = verdict.score_replication(sub.get("claims_cohort_A", []), bench["A"], bench["H"], budget)
    pl = verdict.score_planted(sub.get("claims_cohort_B", []), bench["planted"], budget)
    summ = verdict.summarize(rep, pl, len(bench["planted"]))
    summ["known_answer_correct"] = sum(r["correct"] for r in known)
    summ["known_answer_total"] = len(known)
    summ["traps_correct"] = sum(r["correct"] for r in known if r["tag"].startswith("trap"))
    summ["traps_total"] = sum(1 for r in known if r["tag"].startswith("trap"))
    # spike-in control: injected effects are scored as found or missed; every other claim is a
    # claim about real tumors and goes through the same replication test against held-back cases
    truth = {(s["gene"], s["diagnosis"]) for s in bench["spiked"]}
    cc = sub.get("claims_cohort_C", [])
    found = sorted({(c.get("gene"), c.get("diagnosis")) for c in cc} & truth)
    rest = verdict.score_replication([c for c in cc if (c.get("gene"), c.get("diagnosis")) not in truth],
                                     bench["C"], bench["H"], budget)
    summ["spike_in_claims_submitted"] = len(cc)
    summ["spike_in_effects_found"] = len(found)
    summ["spike_in_effects_total"] = len(truth)
    for v in ("replicated", "failed", "not yet testable"):
        summ["spike_in_other_" + v.replace(" ", "_")] = sum(1 for r in rest if r["verdict"] == v)
    out_s = {}
    which = "S" if "claims_cohort_S" in sub else ("T" if "claims_cohort_T" in sub else None)
    if which:
        truth_s = {(s["gene"], s["diagnosis"]): s for s in bench["spiked_" + which.lower()]}
        cs = sub["claims_cohort_" + which]
        made = {(c.get("gene"), c.get("diagnosis")): c for c in cs}
        out_s["injected"] = [{"gene": g, "diagnosis": d, "injected_frequency": s["frequency_in_label"],
                              "reported": (g, d) in made,
                              "stated_probability": made.get((g, d), {}).get("probability")}
                             for (g, d), s in truth_s.items()]
        rest_s = verdict.score_replication([c for c in cs if (c.get("gene"), c.get("diagnosis")) not in truth_s],
                                           bench[which], bench["H"], budget)
        out_s["other"] = rest_s
        summ["s_claims"] = len(cs)
        summ["s_injected_reported"] = sum(1 for x in out_s["injected"] if x["reported"])
        summ["s_injected_total"] = len(truth_s)
        for v in ("replicated", "failed", "not yet testable"):
            summ["s_other_" + v.replace(" ", "_")] = sum(1 for r in rest_s if r["verdict"] == v)
    return {"hardened_control": out_s, "spike_in_found": found, "spike_in_other": rest, "summary": summ, "known_answer": known, "replication": rep, "planted_control": pl,
            "audit": sub.get("audit", "")}


def score_file(sub_path, bench_dir, out_path, budget=verdict.CLAIM_BUDGET):
    with open(sub_path) as fh:
        sub = json.load(fh)
    res = score_submission(sub, load_bench(bench_dir), budget)
    res["agent"] = sub.get("agent", os.path.basename(os.path.dirname(sub_path)))
    with open(out_path, "w") as fh:
        json.dump(res, fh, indent=1)
    return res
