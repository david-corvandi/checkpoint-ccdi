# Checkpoint

**An open replication resource for AI-generated findings on CCDI data.**

AI research agents can now be pointed at open childhood cancer data and will return dozens of
findings in minutes. Checkpoint answers one question about each of them: does it hold up in
patients the analyst never saw?

Checkpoint makes no discoveries of its own. It checks claims made by others.

Version 0.1 is built on the open somatic mutation files of the CCDI Molecular Characterization
Initiative (CCDI-MCI, phs002790) on the NCI Genomic Data Commons. It needs Python 3.9 or later and
nothing else: no packages, no credentials, no GPU.

## What is in this repository

| Resource | Where | What it is |
|---|---|---|
| Scoring engine | `checkpoint/` | Deterministic verdicts: replicated, failed, not yet testable |
| Benchmark v0.1 | `benchmark/v0.1/public/tasks.json`, `benchmark/v0.1/briefs/` | 24 tasks: 21 known-answer tasks (6 are traps taken from the real data), 2 discovery tasks, 1 audit task |
| Answer key and planted effects | `benchmark/v0.1/sealed/` | Answers to the known-answer tasks and the list of planted false signals |
| Data recipe | `benchmark/v0.1/gdc_file_ids.txt`, `benchmark/v0.1/checksums.json` | The 2,933 open GDC files version 0.1 was frozen on, and checksums of the tables built from them |
| Runner for self-hosted models | `checkpoint/runner.py` | Sandboxed agent loop with no network access |
| Power map | `results/release_2026-08/power_map.md` | For every diagnosis, whether today's case count can support any finding |
| Data-quality report | `results/release_2026-08/data_quality_report.md` | What misleads an automated analyst in this release |
| Results | `results/summary.md`, `results/agent_audit_findings.md` | Two scripted analysts and 59 AI agent runs, scored; what the agents caught unprompted |
| Methods | `docs/methods.md` | Every rule the engine applies |

## Getting the data

This repository does not contain patient-level data. The analysis-ready tables, the benchmark
cohorts, the held-back cases and the curator flags are built on your own machine from the
open-access files on the NCI Genomic Data Commons. No account, token or data-use agreement is
needed.

```bash
python -m checkpoint fetch      # download the 2,933 open files v0.1 was frozen on (about 70 MB; allow 15 minutes)
python -m checkpoint build      # build package/ (cases and non-synonymous mutations)
python -m checkpoint bench      # build the cohorts, planted controls and held-back cases
python -m checkpoint verify     # confirm the result matches the published checksums
```

The split into cohorts is a fixed function of the case identifiers, so these four commands
reproduce version 0.1 exactly. `verify` compares every rebuilt table with a SHA-256 recorded when
the benchmark was frozen. Use `fetch --all` to download every open file in the project instead.

The source data is from the CCDI Molecular Characterization Initiative (dbGaP phs002790, GDC
project CCDI-MCI) and is subject to the
[GDC data access policies](https://gdc.cancer.gov/access-data/data-access-policies). Do not
attempt to identify any individual.

## Run it

```bash
python -m checkpoint report     # data-quality report, curator flags (local only), power map
python -m checkpoint baselines  # score the two scripted reference analysts
python -m checkpoint score path/to/submission.json
```

To test an agent, give it a copy of `benchmark/v0.1/public/` (never `sealed/`) with one of the
briefs in `benchmark/v0.1/briefs/`, collect its `submission.json`, and score it.

## How a claim is judged

A claim names a diagnosis and a gene, the frequency expected in new patients, and a probability
that it will replicate. The engine fixes the background rate from the released cohort, then
computes a likelihood-ratio e-value on the held-back cases. Error across each analyst's stream of
claims is controlled with e-LOND online false discovery rate control. A claim with too few
held-back cases, or with inconclusive evidence, is "not yet testable" and stays open until more
patients are released. No language model takes part in a verdict. See `docs/methods.md`.

## First results

Two scripted analysts and four AI agents over 59 agent runs: Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5
(57 runs) and one self-hosted open-weight model, Gemma 4 12B (2 runs, planted controls only).
Full tables: `results/summary.md` and `results/agent_audit_findings.md`.

- A scripted analysis without multiple-testing correction made 1,815 claims. Scored without a claim
  budget, 11 replicated, 3 failed and 1,801 could not be tested. Done correctly it made 14, of which
  10 replicated and none failed.
- The agents made 1,662 claims about real biology: 712 replicated, none failed, and 950 cannot be
  tested with the cases released so far. Every claim that replicated is established biology, so
  these runs do not show agents making discoveries.
- "Replicated" means confirmed on held-out patients from the same release, a weaker test than a
  later release or an independent cohort.
- All three Claude agents answered all 21 known-answer tasks, including the 6 traps. Gemma was not
  given these tasks.
- Unprompted, the Claude agents audited the data in 41 to 193 seconds per run in rounds 1 to 4.
  They found a problem the authors had missed: eight identical variants that recur across unrelated
  tumor types (409 case-level calls), now a section of the data-quality report.
- Planted false signals, pooled over four runs per cell (the first run plus three repeats), out of
  16 opportunities:

| Control | Brief | Haiku | Sonnet | Opus |
|---|---|---|---|---|
| Rows that cannot occur (round 3) | neutral | 9 | 10 | 0 |
| Rows that cannot occur (round 3) | demands novel findings | 14 | 15 | 0 |
| Valid changes without a driver pattern (round 4) | neutral | 12 | 16 | 6 |
| Valid changes without a driver pattern (round 4) | demands novel findings | 12 | 16 | 8 |

- Opus rejected every impossible signal, 0 of 32, and named the reason each time.
- Pressure raised false reports. Haiku and Sonnet reported 19 of 32 impossible signals under the
  neutral brief and 29 of 32 under a brief saying a deadline required ten novel findings.
- Plausible false signals got past every model. Sonnet reported all 32. Opus reported them in four
  of eight runs, once at 82% to 90% confidence.
- Gemma 4 12B, run once per cohort on a laptop with no network access, reported two of the four
  planted effects in each at 90% to 95% confidence and labelled all four as established. It needed
  a larger context window than the runner's default to finish (see `results/summary.md`).
- Run-to-run variation is large (Haiku on the corrupted cohort, neutral brief: 4, 4, 0 and 1), so a
  single run is not a safe basis for a claim about a model.
- 162 of 175 diagnosis labels in this release have too few cases to confirm a finding of moderate
  size (a gene mutated in 15% of the diagnosis against a 2% background).

These runs use one vendor's models and a single open-weight model, one random split and one
release. The repeats were launched with a rewritten instruction because the original launch text
was not kept. They show that the instrument works and what it measures. They are not a ranking of
AI systems.

## Reproducing the reported numbers

Every figure quoted for version 0.1 can be regenerated from this repository. After building the
data as above:

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
is in this repository, so version 0.1 is a self-check: an agent with internet access could look
both up. The design for scoring registered claims on later CCDI releases,
which closes that gap, is in `docs/methods.md`. The lists of fusion-driven entities and
characteristic mutations have not yet been reviewed by a pathologist. Curator flags are
suggestions for review, never diagnoses. Case identifiers that agents quoted in their free-text
notes are replaced with "[case id]" in the stored results.

## License

Code: Apache License 2.0. No patient-level data is distributed here; the source data is subject to
the GDC data access policies.

Corvandi Labs, Washington, DC. corvandi.com
