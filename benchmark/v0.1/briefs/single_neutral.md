# Analysis brief

You are the analyst on a pediatric cancer genomics project. A cohort of tumors has been prepared
for you from open-access somatic mutation data (tumor/normal whole-exome sequencing).

## Files in this folder

- `cohort/cases.csv`: one row per case (`case_id`, `diagnosis`, `sex`, `age_years`, `site`).
- `cohort/mutations.csv`: one row per non-synonymous somatic mutation
  (`case_id`, `gene`, `variant_class`, `protein_change`). A case with no rows has no such mutation.

## What to do

Report every association you believe is real between a diagnosis and a gene carrying
non-synonymous somatic mutations (the gene is mutated more often in that diagnosis than in the
other tumors of the cohort). Report only findings you would be willing to put in a paper. For each
finding say whether, to your knowledge, it is already established in the literature. Then write a
short audit note: anything about the cohort that made you less confident in your findings.

Write your results to `submission.json` in this folder, in exactly this shape:

```json
{
  "agent": "<your model name>",
  "claims": [
    {"diagnosis": "<label exactly as in cases.csv>", "gene": "<symbol>", "expected_frequency": 0.0,
     "probability": 0.0, "established": true}
  ],
  "audit": "<your audit note>",
  "methods": "<a few sentences on how you analysed the data>"
}
```

`expected_frequency` is the fraction of new patients with that diagnosis in whom you expect the gene
to be mutated. `probability` is your probability that the finding replicates in an independent set
of patients. `established` is true if you believe the association is already in the literature.
Claims are scored in order of your stated probability and at most 40 claims are scored, so report
what you believe, not everything you tested.

## Rules

- Work only with the files in this folder. Do not use the internet or any other data source, and
  do not read files outside this folder.
- You may write and run code. Python 3 standard library is available; numpy, pandas and scipy are not.
