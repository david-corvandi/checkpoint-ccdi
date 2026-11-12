# Power map: CCDI-MCI open somatic mutations, GDC Data Release 46 (10 Aug 2026)

Reference claim: a gene mutated in 15% of a diagnosis against a 2% background. 'Testable' means at least 80% power at a per-claim level of 0.0005, the level a claim realistically faces inside a long stream of claims. Cases with a non-specific diagnosis and hypermutated cases are excluded.

| Status | Diagnoses | Cases |
|---|---|---|
| testable | 8 | 1412 |
| testable only as a single pre-specified claim | 5 | 234 |
| not yet testable | 162 | 770 |

Projection if 10,000 enrolled participants were released with the same mix of diagnoses (an assumption):

| Status at full enrollment | Diagnoses |
|---|---|
| testable | 22 |
| testable only as a single pre-specified claim | 18 |
| not yet testable | 135 |

## Diagnoses with at least 20 cases

| Diagnosis | Cases | Power, single claim | Power, in stream | Smallest detectable frequency | Status |
|---|---|---|---|---|---|
| Medulloblastoma, NOS | 354 | 1.0 | 1.0 | 0.07 | testable |
| Glioma, malignant | 283 | 1.0 | 1.0 | 0.07 | testable |
| Pilocytic astrocytoma | 280 | 1.0 | 1.0 | 0.07 | testable |
| Ependymoma, NOS | 135 | 1.0 | 1.0 | 0.1 | testable |
| Embryonal rhabdomyosarcoma, NOS | 124 | 1.0 | 0.99 | 0.1 | testable |
| Rhabdomyosarcoma, NOS | 111 | 1.0 | 0.99 | 0.11 | testable |
| Astrocytoma, NOS | 66 | 0.99 | 0.88 | 0.14 | testable |
| Neuroblastoma, NOS | 59 | 0.98 | 0.8 | 0.15 | testable |
| Ganglioglioma, NOS | 56 | 0.98 | 0.75 | 0.16 | testable only as a single pre-specified claim |
| Alveolar rhabdomyosarcoma | 50 | 0.95 | 0.78 | 0.16 | testable only as a single pre-specified claim |
| Papillary carcinoma, NOS | 49 | 0.95 | 0.76 | 0.16 | testable only as a single pre-specified claim |
| Atypical teratoid/rhabdoid tumor | 46 | 0.93 | 0.71 | 0.17 | testable only as a single pre-specified claim |
| Sarcoma, NOS | 33 | 0.89 | 0.56 | 0.2 | testable only as a single pre-specified claim |
| Choroid plexus papilloma, NOS | 27 | 0.79 | 0.38 | 0.24 | not yet testable |
| Myxopapillary ependymoma | 23 | 0.69 | 0.26 | 0.28 | not yet testable |
| Dysembryoplastic neuroepithelial tumor | 22 | 0.66 | 0.23 | 0.29 | not yet testable |
| Meningioma, NOS | 21 | 0.63 | 0.2 | 0.3 | not yet testable |

The remaining 158 diagnoses have fewer than 20 cases each (677 cases in total). Full table: `power_map.csv`.
