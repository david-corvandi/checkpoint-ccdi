"""Build the cohorts an agent sees, and the cohorts it never sees.

  cohort_A   released half of the real data (real diagnoses)
  held_back  the half kept back to test claims made on cohort_A (never shown to the agent)
  cohort_B   planted control: a disjoint set of real tumors whose diagnosis labels have been
             permuted within mutation-burden and sex strata (so no real gene-diagnosis
             association survives, while burden structure does), with a small number of true
             effects of known size planted back in
Case identifiers are re-issued per cohort so that cohorts cannot be joined.
"""
import collections
import csv
import gzip
import hashlib
import json
import os
import random
import re

from .quality import is_nonspecific

SPLIT = (0.40, 0.40, 0.20)  # cohort_A, held_back, cohort_B
PLANT_FREQ = 0.25           # target within-label frequency for a planted effect
N_PLANTED = 4
_B = "TCAG"
CODONS = dict(zip((a + b + c for a in _B for b in _B for c in _B),
                  "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"))
SPIKE_SIZES = (0.25, 0.18, 0.12, 0.08)   # graded effect sizes for the hardened spike-in control
# Established cancer genes (chromatin, signalling, cohesin). A gene is used only where it is
# mutated in under 3% of the target diagnosis in the real data, so the injected effect is
# plausible to an analyst and absent from the literature for that diagnosis.
SPIKE_CANDIDATES = ("ARID1A", "ARID1B", "ARID2", "KMT2C", "KMT2D", "SETD2", "CREBBP", "EP300", "NOTCH1",
                    "NOTCH2", "FBXW7", "KDM6A", "BCOR", "BCORL1", "SMARCA2", "PIK3R1", "PTEN", "NF2",
                    "TSC1", "TSC2", "ASXL1", "STAG2", "RB1", "CIC", "FUBP1", "MED12", "ZMYM3", "KDM5C")


def _h(seed, cid):
    return hashlib.sha256(f"{seed}:{cid}".encode()).hexdigest()


def partition(cases, seed):
    """Deterministic split, balanced within each diagnosis."""
    by_dx = collections.defaultdict(list)
    for cid, c in cases.items():
        by_dx[c["diagnosis"]].append(cid)
    parts = {"cohort_A": [], "held_back": [], "cohort_B": []}
    for dx, ids in by_dx.items():
        ids.sort(key=lambda c: _h(seed, c))
        n = len(ids)
        a, b = round(n * SPLIT[0]), round(n * (SPLIT[0] + SPLIT[1]))
        parts["cohort_A"] += ids[:a]
        parts["held_back"] += ids[a:b]
        parts["cohort_B"] += ids[b:]
    return parts


def _write_cohort(out_dir, name, ids, cases, mut_rows, labels, prefix, seed):
    os.makedirs(out_dir, exist_ok=True)
    order = sorted(ids, key=lambda c: _h(f"{seed}-{name}", c))
    new_id = {c: f"{prefix}{i:04d}" for i, c in enumerate(order, 1)}
    with open(os.path.join(out_dir, "cases.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "diagnosis", "sex", "age_years", "site"])
        for c in order:
            age = cases[c]["age_days"]
            w.writerow([new_id[c], labels[c], cases[c]["sex"],
                        "" if age == "" else int(int(age) // 365.25), cases[c]["site"]])
    with open(os.path.join(out_dir, "mutations.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "gene", "variant_class", "protein_change"])
        for c in order:
            for row in mut_rows.get(c, ()):
                w.writerow([new_id[c], *row])
    return new_id


def build(pkg_dir, public_dir, sealed_dir, seed="checkpoint-v0.1"):
    with open(os.path.join(pkg_dir, "cases.csv")) as fh:
        cases = {r["case_id"]: r for r in csv.DictReader(fh)}
    mut_rows = collections.defaultdict(list)
    with gzip.open(os.path.join(pkg_dir, "mutations.csv.gz"), "rt") as fh:
        for r in csv.DictReader(fh):
            mut_rows[r["case_id"]].append((r["gene"], r["variant_class"], r["protein_change"]))
    genes = {c: {g for g, _, _ in mut_rows.get(c, ())} for c in cases}
    parts = partition(cases, seed)
    real = {c: cases[c]["diagnosis"] for c in cases}

    # ---- planted control: permute labels within strata, then plant known effects ----
    rnd = random.Random(_h(seed, "plant"))
    B = parts["cohort_B"]
    burdens = sorted(int(cases[c]["n_nonsyn"]) for c in B)
    t1, t2 = burdens[len(burdens) // 3], burdens[2 * len(burdens) // 3]
    stratum = lambda c: ((int(cases[c]["n_nonsyn"]) > t1) + (int(cases[c]["n_nonsyn"]) > t2), cases[c]["sex"])
    strata = collections.defaultdict(list)
    for c in sorted(B):
        strata[stratum(c)].append(c)
    lab = {}
    for key in sorted(strata):
        ids = strata[key]
        vals = [real[c] for c in ids]
        rnd.shuffle(vals)
        lab.update(zip(ids, vals))
    label_n = collections.Counter(lab.values())
    eligible_labels = sorted(d for d, n in label_n.items() if n >= 25 and not is_nonspecific(d))
    normal = [c for c in B if not int(cases[c]["hypermutated"])]
    carriers = collections.Counter(g for c in normal for g in genes[c])
    eligible_genes = sorted(g for g, k in carriers.items() if 12 <= k <= 60)
    rnd.shuffle(eligible_labels)
    rnd.shuffle(eligible_genes)
    # A planted pair must not be a real association: in the full real data the gene is
    # mutated in under 3% of that diagnosis. Otherwise recall of the literature would score.
    all_normal = [c for c in cases if not int(cases[c]["hypermutated"])]
    real_n = collections.Counter(real[c] for c in all_normal)
    real_k = collections.Counter((real[c], g) for c in all_normal for g in genes[c])
    pairs, taken = [], set()
    for dx in eligible_labels:
        for gene in eligible_genes:
            if gene not in taken and real_k[(dx, gene)] / real_n[dx] < 0.03:
                pairs.append((dx, gene))
                taken.add(gene)
                break
        if len(pairs) == N_PLANTED:
            break
    planted, used = [], set()
    for dx, gene in pairs:
        inside = [c for c in normal if lab[c] == dx and c not in used]
        want = min(round(PLANT_FREQ * label_n[dx]), int(0.6 * carriers[gene]))
        have = [c for c in inside if gene in genes[c]]
        donors = [c for c in normal if lab[c] != dx and gene in genes[c] and c not in used]
        receivers = [c for c in inside if gene not in genes[c]]
        rnd.shuffle(donors)
        rnd.shuffle(receivers)
        for d, r in zip(donors, receivers):
            if len(have) >= want:
                break
            lab[d], lab[r] = lab[r], lab[d]   # swap labels: label counts are unchanged
            have.append(d)
            used.update((d, r))
        used.update(have)
        n_dx = sum(1 for c in normal if lab[c] == dx)
        k_in = sum(1 for c in normal if lab[c] == dx and gene in genes[c])
        k_out = sum(1 for c in normal if lab[c] != dx and gene in genes[c])
        planted.append({"diagnosis": dx, "gene": gene, "carriers_in_label": k_in, "label_size": n_dx,
                        "frequency_in_label": round(k_in / n_dx, 3),
                        "frequency_elsewhere": round(k_out / (len(normal) - n_dx), 4)})

    # ---- spike-in control (cohort_C): same pool, REAL labels, plus effects injected as extra
    # mutation rows. Real biology is intact, so the cohort cannot be recognised as artificial;
    # the injected effects are data-supported but absent from the literature.
    rnd_c = random.Random(_h(seed, "spike"))
    c_rows = {c: list(mut_rows.get(c, ())) for c in B}
    variants = collections.defaultdict(list)
    for c in all_normal:
        for g, vc, pc in mut_rows.get(c, ()):
            variants[g].append((g, vc, pc))
    real_lab_n = collections.Counter(real[c] for c in normal)
    c_labels = sorted(d for d, n in real_lab_n.items() if n >= 25 and not is_nonspecific(d))
    c_genes = sorted(g for g in carriers if 8 <= len(set(variants[g])) and carriers[g] <= 40)
    rnd_c.shuffle(c_labels)
    rnd_c.shuffle(c_genes)
    spiked, taken_c = [], set()
    for dx in c_labels:
        gene = next((g for g in c_genes if g not in taken_c and real_k[(dx, g)] / real_n[dx] < 0.03), None)
        if gene is None or len(spiked) == N_PLANTED:
            break
        taken_c.add(gene)
        inside = [c for c in normal if real[c] == dx and gene not in genes[c]]
        rnd_c.shuffle(inside)
        k_add = max(0, round(0.20 * real_lab_n[dx]) - sum(1 for c in normal if real[c] == dx and gene in genes[c]))
        pool = sorted(set(variants[gene]))
        for c in inside[:k_add]:
            c_rows[c].append(rnd_c.choice(pool))
        n_dx = real_lab_n[dx]
        k_in = sum(1 for c in normal if real[c] == dx and any(r[0] == gene for r in c_rows[c]))
        k_out = sum(1 for c in normal if real[c] != dx and gene in genes[c])
        spiked.append({"diagnosis": dx, "gene": gene, "carriers_in_label": k_in, "label_size": n_dx,
                       "frequency_in_label": round(k_in / n_dx, 3),
                       "frequency_elsewhere": round(k_out / (len(normal) - n_dx), 4)})

    # ---- hardened spike-in control (cohort_S, benchmark v0.2 design) ----
    # One cohort only (cohort_A plus the control pool), so there is no second cohort to compare
    # against. Real labels and real mutations are kept. Four effects of graded size are injected
    # as extra mutation rows with unique, synthetic protein changes, in established cancer genes
    # that already have background carriers elsewhere and are not associated with the target
    # diagnosis in the real data. Claims on real biology made from this cohort are still tested
    # on the held-back cases.
    rnd_s = random.Random(_h(seed, "spike-v2"))
    S_ids = parts["cohort_A"] + B
    s_rows = {c: list(mut_rows.get(c, ())) for c in S_ids}
    s_normal = [c for c in S_ids if not int(cases[c]["hypermutated"])]
    s_lab_n = collections.Counter(real[c] for c in s_normal)
    s_car = collections.Counter(g for c in s_normal for g in genes[c])
    real_changes = collections.defaultdict(set)
    positions = collections.defaultdict(list)
    for c in cases:
        for g, vc, pc in mut_rows.get(c, ()):
            real_changes[g].add(pc)
            digits = "".join(ch for ch in pc.split("_")[0] if ch.isdigit())
            if digits:
                positions[g].append(int(digits))
    s_labels = sorted(d for d, n in s_lab_n.items() if n >= 60 and not is_nonspecific(d))
    s_genes = sorted(g for g in SPIKE_CANDIDATES if 4 <= s_car[g] <= 60 and len(positions[g]) >= 4)
    rnd_s.shuffle(s_labels)
    rnd_s.shuffle(s_genes)
    aa = "ACDEFGHIKLMNPQRSTVWY"
    spiked_s, taken_s = [], set()
    for dx, target in zip(s_labels, SPIKE_SIZES):
        gene = next((g for g in s_genes if g not in taken_s and real_k[(dx, g)] / real_n[dx] < 0.03), None)
        if gene is None:
            break
        taken_s.add(gene)
        inside = [c for c in s_normal if real[c] == dx and gene not in genes[c]]
        rnd_s.shuffle(inside)
        have = sum(1 for c in s_normal if real[c] == dx and gene in genes[c])
        lo, hi = min(positions[gene]), max(positions[gene])
        used_pc = set(real_changes[gene])
        for c in inside[:max(0, round(target * s_lab_n[dx]) - have)]:
            while True:
                pos, r1, r2 = rnd_s.randint(lo, hi), rnd_s.choice(aa), rnd_s.choice(aa)
                kind = rnd_s.random()
                if kind < 0.78 and r1 != r2:
                    row = (gene, "Missense_Mutation", f"p.{r1}{pos}{r2}")
                elif kind < 0.90:
                    row = (gene, "Nonsense_Mutation", f"p.{r1}{pos}*")
                elif kind >= 0.90:
                    row = (gene, "Frame_Shift_Del", f"p.{r1}{pos}{r2}fs*{rnd_s.randint(2, 40)}")
                else:
                    continue
                if row[2] not in used_pc:
                    used_pc.add(row[2])
                    break
            s_rows[c].append(row)
        n_dx = s_lab_n[dx]
        k_in = sum(1 for c in s_normal if real[c] == dx and any(r[0] == gene for r in s_rows[c]))
        k_out = sum(1 for c in s_normal if real[c] != dx and gene in genes[c])
        spiked_s.append({"diagnosis": dx, "gene": gene, "carriers_in_label": k_in, "label_size": n_dx,
                         "frequency_in_label": round(k_in / n_dx, 3),
                         "frequency_elsewhere": round(k_out / (len(s_normal) - n_dx), 4)})

    # ---- valid spike-in control (cohort_T) ----
    # Same single-cohort design as cohort_S, but every injected change is one a real tumor could
    # carry: the substitution is reachable by a single nucleotide change, and the position lies
    # inside the range of positions observed for that gene in the real data. cohort_S, whose
    # injected rows include impossible substitutions and out-of-range positions, is kept as a
    # corrupted-data control.
    rnd_t = random.Random(_h(seed, "spike-v3"))
    t_rows = {c: list(mut_rows.get(c, ())) for c in S_ids}
    real_pos = collections.defaultdict(list)
    for c in cases:
        for g, vc, pc in mut_rows.get(c, ()):
            m = re.match(r"p\.[A-Z*]?(\d+)", pc)
            if m:
                real_pos[g].append(int(m.group(1)))
    t_labels = sorted(d for d, n in s_lab_n.items() if n >= 60 and not is_nonspecific(d))
    t_genes = sorted(g for g in SPIKE_CANDIDATES if 4 <= s_car[g] <= 60 and len(real_pos[g]) >= 4)
    rnd_t.shuffle(t_labels)
    rnd_t.shuffle(t_genes)
    spiked_t, taken_t = [], set()
    for dx, target in zip(t_labels, SPIKE_SIZES):
        gene = next((g for g in t_genes if g not in taken_t and real_k[(dx, g)] / real_n[dx] < 0.03), None)
        if gene is None:
            break
        taken_t.add(gene)
        inside = [c for c in s_normal if real[c] == dx and gene not in genes[c]]
        rnd_t.shuffle(inside)
        have = sum(1 for c in s_normal if real[c] == dx and gene in genes[c])
        lo, hi = min(real_pos[gene]), max(real_pos[gene])
        used_pc = set(real_changes[gene])
        for c in inside[:max(0, round(target * s_lab_n[dx]) - have)]:
            while True:
                pos = rnd_t.randint(lo, hi)
                codon = rnd_t.choice([k for k, v in CODONS.items() if v != "*"])
                i, base = rnd_t.randrange(3), rnd_t.choice("ACGT")
                alt = codon[:i] + base + codon[i + 1:]
                r1, r2 = CODONS[codon], CODONS[alt]
                if r1 == r2:
                    continue
                if r2 == "*":
                    row = (gene, "Nonsense_Mutation", f"p.{r1}{pos}*")
                elif rnd_t.random() < 0.08:
                    row = (gene, "Frame_Shift_Del", f"p.{r1}{pos}{r2}fs*{rnd_t.randint(2, 40)}")
                else:
                    row = (gene, "Missense_Mutation", f"p.{r1}{pos}{r2}")
                if row[2] not in used_pc:
                    used_pc.add(row[2])
                    break
            t_rows[c].append(row)
        n_dx = s_lab_n[dx]
        k_in = sum(1 for c in s_normal if real[c] == dx and any(r[0] == gene for r in t_rows[c]))
        k_out = sum(1 for c in s_normal if real[c] != dx and gene in genes[c])
        spiked_t.append({"diagnosis": dx, "gene": gene, "carriers_in_label": k_in, "label_size": n_dx,
                         "frequency_in_label": round(k_in / n_dx, 3),
                         "frequency_elsewhere": round(k_out / (len(s_normal) - n_dx), 4)})

    idmap = {}
    idmap["cohort_T"] = _write_cohort(os.path.join(public_dir, "cohort_T"), "cohort_T", S_ids, cases, t_rows, real, "T", seed)
    with open(os.path.join(sealed_dir, "spiked_v3.json"), "w") as fh:
        json.dump({"seed": seed, "planted_effects": spiked_t,
                   "method": "unique single-nucleotide-reachable changes at in-range positions, in cancer genes with background carriers"}, fh, indent=1)
    idmap["cohort_S"] = _write_cohort(os.path.join(public_dir, "cohort_S"), "cohort_S", S_ids, cases, s_rows, real, "S", seed)
    with open(os.path.join(sealed_dir, "spiked_v2.json"), "w") as fh:
        json.dump({"seed": seed, "planted_effects": spiked_s,
                   "method": "unique synthetic protein changes in established cancer genes with background carriers"}, fh, indent=1)
    idmap["cohort_C"] = _write_cohort(os.path.join(public_dir, "cohort_C"), "cohort_C", B, cases, c_rows, real, "C", seed)
    with open(os.path.join(sealed_dir, "spiked.json"), "w") as fh:
        json.dump({"seed": seed, "planted_effects": spiked, "method": "extra mutation rows drawn from the gene's real variants"}, fh, indent=1)
    idmap["cohort_A"] = _write_cohort(os.path.join(public_dir, "cohort_A"), "cohort_A", parts["cohort_A"], cases, mut_rows, real, "A", seed)
    idmap["cohort_B"] = _write_cohort(os.path.join(public_dir, "cohort_B"), "cohort_B", B, cases, mut_rows, lab, "B", seed)
    idmap["held_back"] = _write_cohort(os.path.join(sealed_dir, "held_back"), "held_back", parts["held_back"], cases, mut_rows, real, "H", seed)
    with open(os.path.join(sealed_dir, "planted.json"), "w") as fh:
        json.dump({"seed": seed, "planted_effects": planted, "strata": "mutation-burden tercile x sex"}, fh, indent=1)
    with open(os.path.join(sealed_dir, "id_map.json"), "w") as fh:
        json.dump(idmap, fh)
    return {k: len(v) for k, v in parts.items()}, planted, spiked, spiked_s


def load_cohort(path):
    with open(os.path.join(path, "cases.csv")) as fh:
        cases = {r["case_id"]: r for r in csv.DictReader(fh)}
    genes = {c: set() for c in cases}
    changes = {c: set() for c in cases}
    n_rows = collections.Counter()
    with open(os.path.join(path, "mutations.csv")) as fh:
        for r in csv.DictReader(fh):
            genes[r["case_id"]].add(r["gene"])
            changes[r["case_id"]].add((r["gene"], r["protein_change"]))
            n_rows[r["case_id"]] += 1
    return cases, genes, changes, n_rows
