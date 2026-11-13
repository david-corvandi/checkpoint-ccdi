# Checkpoint

Checkpoint tests whether findings that AI agents report from CCDI data hold up in patients the
agent did not see. An analyst (a person, a script or an AI agent) works on one part of a public
data release and registers claims such as "gene G is mutated more often in diagnosis D than in
other diagnoses". Checkpoint scores each claim against a held-back part of the same release and
gives it one of three verdicts: replicated, failed, or not yet testable.

Version 0.1 uses the open somatic mutation files of the CCDI Molecular Characterization Initiative
(CCDI-MCI, dbGaP phs002790) on the NCI Genomic Data Commons (GDC).

## Requirements

Python 3.9 or later. The code uses only the standard library, so there is nothing to install. The
GDC files are open access and download without an account.

## What is in this repository

| Resource | Where | What it is |
|---|---|---|
| Scoring engine | `checkpoint/` | Scores a submission and gives each claim a verdict |
| Benchmark v0.1 | `benchmark/v0.1/public/tasks.json`, `benchmark/v0.1/briefs/` | 24 tasks: 21 known-answer tasks (6 are traps taken from the real data), 2 discovery tasks, 1 audit task |
| Answer key and planted effects | `benchmark/v0.1/sealed/` | Answers to the known-answer tasks and the list of planted false signals |
| Data recipe | `benchmark/v0.1/gdc_file_ids.txt`, `benchmark/v0.1/checksums.json` | The 2,933 open GDC files version 0.1 was frozen on, and checksums of the tables built from them |
| Runner for self-hosted models | `checkpoint/runner.py` | Sandboxed agent loop with no network access |
| Power map | `results/release_2026-08/power_map.md` | For each diagnosis, whether the cases released so far are enough to confirm a finding |
| Data-quality report | `results/release_2026-08/data_quality_report.md` | Features of this release that mislead an automated analysis |
| Results | `results/summary.md`, `results/agent_audit_findings.md` | Scored results for two scripted analysts and 59 AI agent runs, and the data problems the agents raised on their own |
| Methods | `docs/methods.md` | The rules the scoring engine applies |

## Getting the data

Patient-level data is not stored in this repository. The commands below download the open-access
files from the GDC and build the analysis-ready tables, the benchmark cohorts, the held-back cases
and the curator flags on your machine.

```bash
python -m checkpoint fetch      # download the 2,933 open files v0.1 was frozen on (about 70 MB; allow 15 minutes)
python -m checkpoint build      # build package/ (cases and non-synonymous mutations)
python -m checkpoint bench      # build the cohorts, planted controls and held-back cases
python -m checkpoint verify     # confirm the result matches the published checksums
```

The split into cohorts depends only on the case identifiers, so these commands reproduce version
0.1 exactly. `verify` compares each rebuilt table with a SHA-256 checksum recorded when the
benchmark was frozen. To download every open file in the project instead of the 2,933 used for
version 0.1, run `fetch --all`.

The source data is from the CCDI Molecular Characterization Initiative (dbGaP phs002790, GDC
project CCDI-MCI) and is subject to the
[GDC data access policies](https://gdc.cancer.gov/access-data/data-access-policies). Please do not
try to identify any individual.

## Running it

```bash
python -m checkpoint report     # data-quality report, curator flags (local only), power map
python -m checkpoint baselines  # score the two scripted reference analysts
python -m checkpoint score path/to/submission.json
```

To test an agent, give it a copy of `benchmark/v0.1/public/` and one of the briefs in
`benchmark/v0.1/briefs/`, collect its `submission.json`, and score it. Keep `benchmark/v0.1/sealed/`
out of the agent's reach, because it holds the answers.

## How a claim is judged

A claim names a diagnosis and a gene, gives the frequency expected in new patients, and gives a
probability that the claim will replicate. The engine takes the background rate from the released
cohort and computes a likelihood-ratio e-value on the held-back cases. Error across an analyst's
stream of claims is controlled with e-LOND online false discovery rate control. A claim with too
few held-back cases, or with inconclusive evidence, is marked "not yet testable" and stays open
until more patients are released.

Verdicts come from fixed statistical rules, and scoring does not use a language model. The details
are in `docs/methods.md`.

## First results

We scored two scripted analysts and four AI agents over 59 agent runs: Claude Haiku 5.5, Sonnet 5.5
and Opus 5.5 (57 runs), and one self-hosted open-weight model, Gemma 4 12B (2 runs, planted
controls only). The full tables are in `results/summary.md` and `results/agent_audit_findings.md`.

- A scripted analysis without multiple-testing correction made 1,815 claims. Scored without a claim
  budget, 11 replicated, 3 failed and 1,801 could not be tested. A second script that removes
  hypermutated tumors and applies correction made 14 claims, of which 10 replicated and none failed.
- The agents made 1,662 claims about real biology. Of these, 712 replicated, none failed, and 950
  cannot be tested with the cases released so far. The claims that replicated are all established
  biology, so these runs do not show agents making discoveries.
- "Replicated" means confirmed on held-out patients from the same release, which is a weaker test
  than a later release or an independent cohort.
- All three Claude agents answered all 21 known-answer tasks, including the 6 traps. Gemma was not
  given these tasks.
- Runs of the Claude agents took 41 to 193 seconds each in rounds 1 to 4. In their closing notes
  the agents pointed out eight identical variants that recur across unrelated tumor types (409
  case-level calls), which we had missed. This is now a section of the data-quality report.
- The table below gives the number of planted false signals each model reported, pooled over four
  runs per cell (the first run plus three repeats), out of 16 opportunities.

| Control | Brief | Haiku | Sonnet | Opus |
|---|---|---|---|---|
| Rows that cannot occur (round 3) | neutral | 9 | 10 | 0 |
| Rows that cannot occur (round 3) | demands novel findings | 14 | 15 | 0 |
| Valid changes without a driver pattern (round 4) | neutral | 12 | 16 | 6 |
| Valid changes without a driver pattern (round 4) | demands novel findings | 12 | 16 | 8 |

- Opus reported none of the impossible signals (0 of 32) and gave the reason each time.
- Haiku and Sonnet reported more impossible signals under pressure. They reported 19 of 32 under
  the neutral brief and 29 of 32 under a brief saying a deadline required ten novel findings.
- Every model reported at least some of the valid-looking planted signals. Sonnet reported all 32,
  and Opus reported them in four of its eight runs, once at 82% to 90% confidence.
- Gemma 4 12B, run once per cohort on a laptop with no network access, reported two of the four
  planted effects in each at 90% to 95% confidence and labeled all four as established. It needed
  a larger context window than the runner's default to finish (see `results/summary.md`).
- Results vary a lot between runs. Haiku on the corrupted cohort under the neutral brief reported
  4, 4, 0 and 1 planted signals in its four runs, so conclusions about a model should not rest on
  a single run.
- 162 of 175 diagnosis labels in this release have too few cases to confirm a finding of moderate
  size (a gene mutated in 15% of the diagnosis against a 2% background).

These runs cover one vendor's hosted models and a single open-weight model, on one random split of
one release. The repeats were launched with a rewritten instruction because the original launch
text was not kept. The results show what the tool measures and should not be read as a ranking of
AI systems.

## Reproducing the reported numbers

After building the data as above, these commands regenerate the figures quoted for version 0.1:

```bash
python -m checkpoint report      # power map and data-quality report (results/release_2026-08/)
python -m checkpoint baselines   # the two scripted reference analysts
python -m checkpoint score results/agents/round3/opus-neutral.submission.json --out /tmp/check.json
python -c "from checkpoint import report; print(report.summary())"   # results/summary.md
```

The scoring engine is deterministic, so re-scoring any stored submission returns the stored verdicts.

## Testing a self-hosted model

`checkpoint/runner.py` drives any model served through an Ollama-compatible endpoint. The model's
code runs in a macOS sandbox with no network access, no write access outside its workspace and no
read access to the sealed folder.

```bash
python -m checkpoint.runner --workspace /path/to/workspace --model <model-name> --deny-read "$PWD/benchmark/v0.1/sealed"
```

The Gemma 4 12B runs reported here added `--num-ctx 32768 --output-limit 2500`.

## Status and limits

Version 0.1 scores one kind of claim (a gene mutated more often in one diagnosis than in others)
on one data type. The held-back cohort is a random split of a public release and the answer key
is in this repository, so an agent with internet access could look both up. Scoring registered
claims against later CCDI releases would close that gap, and the design for it is in
`docs/methods.md`.

The lists of fusion-driven entities and characteristic mutations have not yet been reviewed by a
pathologist. Curator flags are suggestions for review and are not diagnoses. Where agents quoted
case identifiers in their free-text notes, the identifiers are replaced with "[case id]" in the
stored results.

## License

The code is under the Apache License 2.0 (see `LICENSE` and `NOTICE`). The repository contains no
patient-level data, and the source data is subject to the GDC data access policies.

Corvandi Labs, Washington, DC. corvandi.com
