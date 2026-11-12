# What the agents caught without being asked

Source: the free-text audit note each agent wrote at the end of its run, across 23 runs. The agents were asked only what made them less confident in their findings. An issue is counted when the note mentions it, by keyword, so the counts are approximate.

| Issue in the data | Runs that raised it |
|---|---|
| Hypermutated tumors distorting enrichment | 21 of 23 |
| Vague, missing or pooled diagnosis labels | 23 of 23 |
| Groups too small to support a finding | 18 of 23 |
| Identical variants recurring across unrelated tumors (likely artifacts) | 18 of 23 |
| Residue numbering that differs from clinical names | 10 of 23 |
| Drivers invisible to mutation files (fusions, copy number) | 6 of 23 |

Time per run, hosted models: 41 to 193 seconds, median 100. Self-hosted open-weight model on a laptop: 46 to 47 minutes.

The recurring-variant issue was not known to the authors before the agents raised it. It is now a section of the data-quality report. Residue numbering was prompted by two known-answer tasks in round 1.
