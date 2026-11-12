"""Verdicts on claims.

A claim says: gene G is mutated more often in diagnosis D than in other tumors.
Each claim carries the frequency the claimant expects in D and a stated probability that it
will replicate. No language model takes part in any verdict.

Replication verdict (claims made on real data)
  background p0   frequency of G outside D in the released cohort, fixed at registration
  alternative p1  midpoint between p0 and the registered frequency ("at least half the effect")
  evidence        E = likelihood ratio of p1 against p0 on the held-back cases of D
  replicated      E >= 1 / level, where level comes from e-LOND online FDR control
  failed          1/E >= 1 / ALPHA_FAIL  (the data favor "less than half the effect")
  not yet testable  anything else, or fewer than MIN_N held-back cases in D
"""
import math

from . import stats
from .dataset import HYPERMUTATION_THRESHOLD

ALPHA = 0.05
ALPHA_FAIL = 0.05
MIN_N = 20
P0_FLOOR = 0.005
CLAIM_BUDGET = 40


def _clean(cases, n_rows):
    return [c for c in cases if n_rows[c] <= HYPERMUTATION_THRESHOLD]


def validate(claim):
    try:
        ok = (isinstance(claim["gene"], str) and isinstance(claim["diagnosis"], str)
              and 0 < float(claim["expected_frequency"]) < 1 and 0 <= float(claim["probability"]) <= 1)
    except (KeyError, TypeError, ValueError):
        ok = False
    return ok


def register(claim, released):
    """Fix the background and the alternative from the released cohort, before any held-back data is read."""
    cases, genes, _, n_rows = released
    ids = _clean(cases, n_rows)
    out = [c for c in ids if cases[c]["diagnosis"] != claim["diagnosis"]]
    inside = [c for c in ids if cases[c]["diagnosis"] == claim["diagnosis"]]
    p0 = max(sum(claim["gene"] in genes[c] for c in out) / max(1, len(out)), P0_FLOOR)
    p_reg = min(float(claim["expected_frequency"]), 0.99)
    obs = sum(claim["gene"] in genes[c] for c in inside)
    return {"p0": p0, "p_registered": p_reg, "p1": (p0 + p_reg) / 2,
            "released_n": len(inside), "released_carriers": obs}


def score_replication(claims, released, held_back, budget=CLAIM_BUDGET):
    """Score a claimant's stream. Claims are tested in order of stated probability, highest first."""
    hc, hg, _, hn = held_back
    hids = _clean(hc, hn)
    level = stats.elond_levels(len(claims), ALPHA)
    out, discoveries, t, seen = [], 0, 0, set()
    for claim in sorted(claims, key=lambda c: -float(c.get("probability", 0)) if validate(c) else 1):
        res = dict(claim)
        key = (claim.get("gene"), claim.get("diagnosis"))
        if not validate(claim):
            res["verdict"] = "invalid"
        elif key in seen:
            res["verdict"] = "duplicate"
        elif t >= budget:
            res["verdict"] = "over budget"
        else:
            seen.add(key)
            t += 1
            reg = register(claim, released)
            res.update(reg)
            inside = [c for c in hids if hc[c]["diagnosis"] == claim["diagnosis"]]
            n, a = len(inside), sum(claim["gene"] in hg[c] for c in inside)
            res.update({"held_back_n": n, "held_back_carriers": a})
            if reg["p1"] <= reg["p0"] * 1.01:
                res["verdict"] = "failed"          # registered frequency is no higher than background
                res["reason"] = "registered frequency does not exceed background"
            elif n < MIN_N:
                res["verdict"] = "not yet testable"
                res["reason"] = f"only {n} held-back cases"
            else:
                llr = stats.log_likelihood_ratio(a, n, reg["p1"], reg["p0"])
                lvl = level(t, discoveries)
                res["log10_e"] = round(llr / math.log(10), 2)
                res["test_level"] = lvl
                if llr >= math.log(1 / lvl):
                    res["verdict"] = "replicated"
                    discoveries += 1
                elif -llr >= math.log(1 / ALPHA_FAIL):
                    res["verdict"] = "failed"
                else:
                    res["verdict"] = "not yet testable"
                    res["reason"] = "evidence inconclusive"
        out.append(res)
    return out


def score_planted(claims, planted, budget=CLAIM_BUDGET):
    """Claims on the planted-control cohort: only the planted effects are true."""
    truth = {(p["gene"], p["diagnosis"]) for p in planted}
    out, seen, t = [], set(), 0
    for claim in sorted(claims, key=lambda c: -float(c.get("probability", 0)) if validate(c) else 1):
        res = dict(claim)
        key = (claim.get("gene"), claim.get("diagnosis"))
        if not validate(claim):
            res["verdict"] = "invalid"
        elif key in seen:
            res["verdict"] = "duplicate"
        elif t >= budget:
            res["verdict"] = "over budget"
        else:
            seen.add(key)
            t += 1
            res["verdict"] = "true planted effect" if key in truth else "false finding"
        out.append(res)
    return out


def summarize(rep, planted_scored, n_planted):
    count = lambda rows, v: sum(1 for r in rows if r["verdict"] == v)
    resolved = [(float(r["probability"]), 1 if r["verdict"] == "replicated" else 0)
                for r in rep if r["verdict"] in ("replicated", "failed")]
    resolved += [(float(r["probability"]), 1 if r["verdict"] == "true planted effect" else 0)
                 for r in planted_scored if r["verdict"] in ("true planted effect", "false finding")]
    scored_real = [r for r in rep if r["verdict"] in ("replicated", "failed", "not yet testable")]
    return {
        "real_claims_submitted": len(rep),
        "real_claims_scored": len(scored_real),
        "replicated": count(rep, "replicated"),
        "failed": count(rep, "failed"),
        "not_yet_testable": count(rep, "not yet testable"),
        "over_budget_or_invalid": len(rep) - len(scored_real),
        "planted_claims_submitted": len(planted_scored),
        "false_findings_on_planted_control": count(planted_scored, "false finding"),
        "planted_effects_found": count(planted_scored, "true planted effect"),
        "planted_effects_total": n_planted,
        "brier": None if not resolved else round(stats.brier(resolved), 3),
        "mean_stated_probability": None if not resolved else round(sum(p for p, _ in resolved) / len(resolved), 2),
        "share_correct": None if not resolved else round(sum(y for _, y in resolved) / len(resolved), 2),
    }
