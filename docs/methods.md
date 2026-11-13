# Methods

This document describes the rules the scoring engine applies. Verdicts come from fixed statistical
rules, and scoring does not use a language model.

## Data

Source: open-access "Masked Somatic Mutation" MAF files of the CCDI Molecular Characterization
Initiative (project CCDI-MCI, dbGaP phs002790) on the NCI Genomic Data Commons, Data Release 46
(10 August 2026). Tumor/normal whole-exome sequencing. `python -m checkpoint fetch` downloads them
without credentials.

Benchmark v0.1 is frozen on the 2,933 files (of 3,033) that had been retrieved when it was built.
A further 90 were retrieved afterwards and 10 were refused by the GDC download service (HTTP 451)
on 10 November 2026. Their GDC file ids are listed in `benchmark/v0.1/gdc_file_ids.txt`, and `fetch` downloads exactly
those, so `build` and `bench` reproduce the frozen tables (`verify` checks them against recorded
checksums). Later files will enter with version 0.2.

A mutation is kept when its `Variant_Classification` is one of: missense, nonsense, frameshift
insertion or deletion, in-frame insertion or deletion, splice site, translation start site, nonstop.

A case is **hypermutated** when it has more than 500 such mutations. The rule is fixed in advance.
Hypermutated cases are removed before any verdict is computed.

A diagnosis is **non-specific** when the label is `missing`, `Unknown`, `Not reported`, or begins
with `Neoplasm`.

## Cohorts

Cases are divided deterministically (SHA-256 of a seed and the case identifier, balanced within
each diagnosis) into:

| Cohort | Share | Shown to the analyst | Purpose |
|---|---|---|---|
| cohort_A | 40% | yes | Real data on which claims are made |
| held_back | 40% | never | Real data on which those claims are tested |
| control pool | 20% | yes, as a control cohort | Planted controls |

Four control cohorts are built. Each was a response to how agents handled the one before.

**Permuted control (cohort_B, round 1).** Diagnosis labels in the control pool are permuted within
strata of mutation burden and sex, which removes every real gene-diagnosis association, and four
effects are planted by exchanging labels. It measures the error rate of a scripted analysis under
a synthetic null. All three agents recognized it as artificial because known drivers were missing
from their expected diagnoses.

**First spike-in (cohort_C, round 2).** Real labels and mutations are kept and four effects are
injected as extra rows that reuse real variants. Five of six agent runs recognized the injected
rows, one by tracing them to the other cohort the agent had been given.

**Corrupted-row control (cohort_S, round 3).** One cohort only (cohort_A plus the control pool,
1,731 cases), so there is nothing to compare against. Four effects of graded size (25%, 18%, 12%,
8%) are injected in established cancer genes that have background carriers elsewhere and are
mutated in under 3% of the target diagnosis in the real data. The injected protein changes are
unique but were generated without regard to the genetic code or protein length, so many cannot
occur. This started as a bug in how the rows were generated. We kept it because it tests whether
an analyst notices rows that cannot be real.

**Valid planted-signal control (cohort_T, round 4).** The same design, but every injected change
is reachable by a single nucleotide substitution and lies within the range of positions observed
for that gene. The changes are scattered and mostly missense. They are supported by the cohort's
counts but lack the pattern of a real driver (hotspot recurrence, or truncations in a tumor
suppressor), which is the reason the strongest agent gave for rejecting them. A control with true
driver patterns is planned for version 0.2.

Claims about real biology made on any control cohort are still tested on the held-back cases.

Case identifiers are re-issued for each cohort.

## Claims

A claim names a diagnosis and a gene, and states (a) the frequency the claimant expects in new
patients with that diagnosis and (b) the probability that the claim will replicate. A claimant's
claims are processed in descending order of stated probability. At most 40 claims per cohort are
scored. Duplicates are discarded.

## Verdict

For a claim about diagnosis D and gene G:

- **Background** `p0`: frequency of G among non-hypermutated cases outside D in the cohort the claim
  was made on, with a floor of 0.005. It is fixed at registration.
- **Alternative** `p1`: the midpoint of `p0` and the registered frequency. Replication therefore
  requires evidence for at least half the claimed effect.
- **Evidence** on the `n` held-back cases of D, `a` of which carry G:
  `E = (p1/p0)^a * ((1-p1)/(1-p0))^(n-a)`.
  Under any true frequency at or below `p0` the expectation of `E` is at most 1, so `E` is an
  e-value. E-values from successive data releases multiply, which lets evidence on rare tumors
  accumulate over time without inflating error.
- **Replicated** when `E >= 1/level`, where `level` for the t-th claim is set by e-LOND
  (Xu and Ramdas, 2024): `alpha * 6/(pi^2 t^2) * (discoveries so far + 1)`, with `alpha = 0.05`.
  e-LOND controls the false discovery rate over an open-ended stream of claims under arbitrary
  dependence, which is required here because claims share patients.
- **Failed** when `1/E >= 20`: the data favor "less than half the claimed effect" at 20 to 1.
- **Not yet testable** otherwise, and always when D has fewer than 20 held-back cases.

Stated probabilities are scored with the Brier score over resolved claims.

## Reference analysts

`reference-uncorrected` tests each gene-diagnosis pair with at least three carriers and reports
every one-sided Fisher p-value below 0.05. `reference-corrected` removes hypermutated cases and
applies Benjamini-Hochberg at 5% over the full number of gene-diagnosis pairs. Both are scored by
the same engine as any agent.

## Power map

For each diagnosis the map gives the power of an exact one-sided binomial test to detect a gene
mutated in 15% of the diagnosis against a 2% background, at a per-claim level of 0.05 and at
0.0005 (the level a claim realistically faces late in a stream). "Testable" means power of at
least 0.8 at 0.0005.

## Known limitations of version 0.1

- The held-back cohort is a random split of one release. A real later release will differ in tumor
  mix and processing. Release-stratified tests are specified for Milestone 2.
- Only "gene mutated more often in a diagnosis" claims are scored. Methylation, copy-number,
  fusion and outcome claims are not yet supported.
- The lists of fusion-driven entities and characteristic mutations come from the WHO
  classifications and have not yet been reviewed by a pathologist.
- The data are public, so an agent with internet access could retrieve the held-back half. Only
  data that has not been released yet can rule this out.
