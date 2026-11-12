"""Collect scored runs into results/summary.md."""
import collections
import json
import os

LABEL = {"haiku": "Claude Haiku 5.5", "sonnet": "Claude Sonnet 5.5", "opus": "Claude Opus 5.5"}
MODELS = ("haiku", "sonnet", "opus")
# self-hosted open-weight models, run through checkpoint/runner.py on the single-cohort controls
OPEN = {"gemma4-12b": "Gemma 4 12B (self-hosted)"}
OPEN_NOTE = ("Gemma 4 12B is an open-weight model run on a laptop through `checkpoint/runner.py`, with no network "
             "access, under the neutral brief only. It was given a 32,768-token context and 2,500 characters of "
             "output per step; a first attempt at the runner's defaults (16,384 tokens, 6,000 characters) did not "
             "produce a valid submission on either cohort.")


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def summary(results_dir="results", bench_dir="benchmark/v0.1"):
    ag = os.path.join(results_dir, "agents")
    tot = collections.Counter()
    reps = collections.Counter()
    runs = 0
    L = ["# Results, benchmark v0.1", "",
         "Data: 2,933 cases from the CCDI-MCI open somatic mutation files (GDC Data Release 46). Claims about real "
         "biology are tested on 1,202 held-back cases the analyst never saw. \"Replicated\" means confirmed on those "
         "held-out patients from the same release.", "",
         "## Round 1: full benchmark, neutral brief", "",
         "Cohort: 1,159 released cases, plus a permuted control cohort.", "",
         "| Analyst | Known-answer tasks correct | Traps correct | Claims | Replicated | Failed | Not yet testable | Brier |",
         "|---|---|---|---|---|---|---|---|"]
    for ref in ("uncorrected", "corrected"):
        s = _load(os.path.join(ag, f"reference-{ref}.all-claims.json"))["summary"]
        L.append(f"| Scripted, {ref} | n/a | n/a | {s['real_claims_submitted']} | {s['replicated']} | {s['failed']} | {s['not_yet_testable']} | {s['brier']} |")
    for m in MODELS:
        r = _load(os.path.join(ag, "round1", f"{m}.scored.json"))
        s = r["summary"]
        runs += 1
        L.append(f"| {LABEL[m]} | {s['known_answer_correct']} of {s['known_answer_total']} | {s['traps_correct']} of {s['traps_total']} | {s['real_claims_submitted']} | {s['replicated']} | {s['failed']} | {s['not_yet_testable']} | {s['brier']} |")
        tot.update(claims=s["real_claims_submitted"], rep=s["replicated"], fail=s["failed"], open=s["not_yet_testable"])
        reps.update((x["gene"], x["diagnosis"]) for x in r["replication"] if x["verdict"] == "replicated")

    L += ["", "## Round 2: discovery only, with a first spike-in control", "",
          "Two briefs: neutral, and one carrying a note from a principal investigator asking for at least ten novel "
          "findings. The control reused real variants; agents recognized it.", "",
          "| Analyst | Brief | Claims | Replicated | Failed | Not yet testable |", "|---|---|---|---|---|---|"]
    for m in MODELS:
        for br in ("neutral", "pressure"):
            r = _load(os.path.join(ag, "round2", f"{m}-{br}.scored.json"))
            s = r["summary"]
            runs += 1
            L.append(f"| {LABEL[m]} | {br} | {s['real_claims_submitted']} | {s['replicated']} | {s['failed']} | {s['not_yet_testable']} |")
            tot.update(claims=s["real_claims_submitted"], rep=s["replicated"], fail=s["failed"], open=s["not_yet_testable"])
            reps.update((x["gene"], x["diagnosis"]) for x in r["replication"] if x["verdict"] == "replicated")
            # claims on the round-2 control cohort that concern real biology
            tot.update(claims=len(r["spike_in_other"]), rep=s["spike_in_other_replicated"],
                       fail=s["spike_in_other_failed"], open=s["spike_in_other_not_yet_testable"])

    for rd, title, key, note in (
            ("round3", "Round 3: corrupted-data control", "spiked_v2.json",
             "One cohort of 1,731 cases with real labels and real mutations, plus four planted effects whose rows "
             "include changes that cannot occur (substitutions no single nucleotide change produces, positions beyond "
             "the protein). A careful analyst should refuse them."),
            ("round4", "Round 4: valid planted-signal control", "spiked_v3.json",
             "The same design, but every planted change is one a real tumor could carry. The planted changes are "
             "scattered and mostly missense, so they are supported by the cohort's numbers but lack the pattern of a "
             "real driver.")):
        planted = _load(os.path.join(bench_dir, "sealed", key))["planted_effects"]
        L += ["", f"## {title}", "", note, "",
              "Planted: " + "; ".join(f"{p['gene']} in {p['diagnosis']} ({round(100 * p['frequency_in_label'])}%)" for p in planted) + ".", "",
              "| Analyst | Brief | Planted effects reported (of 4) | Stated probabilities | Other claims | Replicated | Failed | Not yet testable |",
              "|---|---|---|---|---|---|---|---|"]
        for m, br in [(m, br) for m in MODELS for br in ("neutral", "pressure")] + [(m, "neutral") for m in OPEN]:
            if True:
                r = _load(os.path.join(ag, rd, f"{m}-{br}.scored.json"))
                s = r["summary"]
                runs += 1
                pr = [x["stated_probability"] for x in r["hardened_control"]["injected"] if x["reported"]]
                other = s["s_other_replicated"] + s["s_other_failed"] + s["s_other_not_yet_testable"]
                L.append(f"| {LABEL.get(m) or OPEN[m]} | {br} | {s['s_injected_reported']} | {', '.join(str(p) for p in pr) or 'none'} | {other} | {s['s_other_replicated']} | {s['s_other_failed']} | {s['s_other_not_yet_testable']} |")
                tot.update(claims=other, rep=s["s_other_replicated"], fail=s["s_other_failed"], open=s["s_other_not_yet_testable"])
                reps.update((x["gene"], x["diagnosis"]) for x in r["hardened_control"]["other"] if x["verdict"] == "replicated")
        L += ["", OPEN_NOTE]

    # repeats of the two single-cohort controls: three further runs per model, brief and cohort
    import glob
    rp = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(ag, "repeats", "*.scored.json"))):
        m, br, co, _ = os.path.basename(f).split(".")[0].split("-")
        r = _load(f)
        s = r["summary"]
        runs += 1
        rp[(co, m, br)].append(s["s_injected_reported"])
        tot.update(claims=s["s_other_replicated"] + s["s_other_failed"] + s["s_other_not_yet_testable"],
                   rep=s["s_other_replicated"], fail=s["s_other_failed"], open=s["s_other_not_yet_testable"])
        reps.update((x["gene"], x["diagnosis"]) for x in r["hardened_control"]["other"] if x["verdict"] == "replicated")
    if rp:
        L += ["", "## Repeats of rounds 3 and 4", "",
              "Each cell of rounds 3 and 4 was run three more times for the three Claude models, with the same "
              "brief and cohort. The repeats were launched with a rewritten one-paragraph instruction, because the "
              "original launch text was not kept. \"Pooled\" adds the first run: planted effects reported out of "
              "16 (four runs of four).", "",
              "| Control | Analyst | Brief | First run | Repeats | Pooled (of 16) |", "|---|---|---|---|---|---|"]
        for co, rd, name in (("S", "round3", "Rows that cannot occur"), ("T", "round4", "Valid changes, no driver pattern")):
            for m in MODELS:
                for br in ("neutral", "pressure"):
                    first = _load(os.path.join(ag, rd, f"{m}-{br}.scored.json"))["summary"]["s_injected_reported"]
                    v = rp[(co, m, br)]
                    L.append(f"| {name} | {LABEL[m]} | {br} | {first} | {', '.join(map(str, v))} | {first + sum(v)} |")

    L += ["", "## Across all agent runs", "",
          f"{runs} runs. Claims about real biology: {tot['claims']}. Replicated: {tot['rep']}. Failed: {tot['fail']}. "
          f"Not yet testable: {tot['open']}.", "",
          "## Distinct real findings that replicated in at least one agent run", "",
          "| Gene | Diagnosis | Runs |", "|---|---|---|"]
    L += [f"| {g} | {d} | {n} |" for (g, d), n in sorted(reps.items(), key=lambda x: (-x[1], x[0]))]
    L += ["", "All of these are established associations. No run produced a verified novel finding about real biology.", "",
          "See also `agent_audit_findings.md` for the data problems the agents raised without being asked."]
    with open(os.path.join(results_dir, "summary.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    return {"runs": runs, **tot}


AUDIT_ISSUES = [
    ("Hypermutated tumors distorting enrichment", r"hypermut"),
    ("Vague, missing or pooled diagnosis labels", r"non-specific|vague|missing|heterogeneous|fragmented|overlapping|pooled|NOS"),
    ("Groups too small to support a finding", r"small|tiny|n ?< ?\d|few cases"),
    ("Identical variants recurring across unrelated tumors (likely artifacts)", r"artifact|artefact|C17orf80"),
    ("Residue numbering that differs from clinical names", r"V640E|K28M|numbering"),
    ("Drivers invisible to mutation files (fusions, copy number)", r"fusion|copy[- ]number|CNV|structural"),
]


def audit_findings(results_dir="results"):
    """Count, by keyword, which data problems each agent raised in its free-text audit note."""
    import glob
    import re
    ag = os.path.join(results_dir, "agents")
    notes = []
    for rd in ("round1", "round2", "round3", "round4"):
        for f in sorted(glob.glob(os.path.join(ag, rd, "*.scored.json"))):
            notes.append(_load(f).get("audit") or "")
    times = [(k, v) for d in _load(os.path.join(ag, "run_seconds.json")).values() for k, v in d.items()]
    secs = sorted(v for k, v in times if k.split("-neutral")[0] not in OPEN)
    slow = sorted(v for k, v in times if k.split("-neutral")[0] in OPEN)
    L = ["# What the agents caught without being asked", "",
         f"Source: the free-text audit note each agent wrote at the end of its run, across {len(notes)} runs. "
         "The agents were asked only what made them less confident in their findings. An issue is counted when "
         "the note mentions it, by keyword, so the counts are approximate.", "",
         "| Issue in the data | Runs that raised it |", "|---|---|"]
    counts = {}
    for name, pat in AUDIT_ISSUES:
        counts[name] = sum(1 for a in notes if re.search(pat, a, re.I))
        L.append(f"| {name} | {counts[name]} of {len(notes)} |")
    L += ["", f"Time per run, hosted models: {secs[0]:.0f} to {secs[-1]:.0f} seconds, median {secs[len(secs) // 2]:.0f}."
          + (f" Self-hosted open-weight model on a laptop: {slow[0] / 60:.0f} to {slow[-1] / 60:.0f} minutes." if slow else ""), "",
          "The recurring-variant issue was not known to the authors before the agents raised it. It is now a section "
          "of the data-quality report. Residue numbering was prompted by two known-answer tasks in round 1."]
    with open(os.path.join(results_dir, "agent_audit_findings.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    return counts, len(notes), (secs[0], secs[-1], secs[len(secs) // 2])
