# Data-quality report: CCDI-MCI open somatic mutations, GDC Data Release 46 (10 Aug 2026)

Cases with an open somatic mutation file analyzed: **2933**, across 182 distinct diagnosis labels.

## What will mislead an automated analyst

| Issue | Cases | Why it matters |
|---|---|---|
| No specific diagnosis (missing, unknown, or 'Neoplasm ...') | 503 (17.1%) | These cases dilute every 'this diagnosis versus the rest' comparison |
| Diagnosis ends in 'NOS' | 1228 (41.9%) | Molecular subtypes are pooled, which hides subtype-specific signals |
| Vital status not reported | 2166 (73.8%) | Survival claims cannot be tested in the open tier |
| Hypermutated tumors (more than 500 non-synonymous mutations) | 17 (0.6%) | A single such case can make hundreds of genes look enriched in a small group |
| Tumor types whose defining alteration is not a point mutation | 611 (20.8%) | A mutation-only analysis reports 'no driver found' for these tumors |
| Cases with no non-synonymous mutation | 225 (7.7%) | Expected in pediatric tumors; not a data error |

## Non-specific labels

| Label | Cases |
|---|---|
| Neoplasm, uncertain whether benign or malignant | 186 |
| missing | 136 |
| Neoplasm, malignant | 125 |
| Unknown | 42 |
| Neoplasm, benign | 8 |
| Neoplasm, metastatic | 4 |
| Neoplasm, malignant, uncertain whether primary or metastatic | 2 |

## Tumor types a mutation file cannot explain

| Diagnosis | Cases | Defining alteration |
|---|---|---|
| Pilocytic astrocytoma | 280 | KIAA1549::BRAF fusion (tandem duplication) |
| Ependymoma, NOS | 135 | ZFTA or YAP1 fusions; posterior fossa groups defined by methylation |
| Neuroblastoma, NOS | 59 | MYCN amplification and segmental copy-number change |
| Alveolar rhabdomyosarcoma | 50 | PAX3::FOXO1 or PAX7::FOXO1 fusion |
| Atypical teratoid/rhabdoid tumor | 46 | SMARCB1 loss, often by deletion |
| Ewing sarcoma | 11 | EWSR1::FLI1 and related fusions |
| Desmoplastic small round cell tumor | 11 | EWSR1::WT1 fusion |
| Synovial sarcoma, NOS | 9 | SS18::SSX fusion |
| Alveolar soft part sarcoma | 6 | ASPSCR1::TFE3 fusion |
| Infantile fibrosarcoma | 4 | ETV6::NTRK3 fusion |

## Hypermutated cases

17 cases carry more than 500 non-synonymous mutations each (range 502 to 15,731).

| Diagnosis | Hypermutated cases |
|---|---|
| Glioma, malignant | 8 |
| Adenocarcinoma, NOS | 2 |
| Neoplasm, malignant | 2 |
| Astrocytoma, NOS | 1 |
| Glioblastoma | 1 |
| Medulloblastoma, NOS | 1 |
| Oligoastrocytoma | 1 |
| Unknown | 1 |

## Residue numbering that defeats a text search

| Mutation as clinicians name it | Cases found under that name | Name used in these files | Cases |
|---|---|---|---|
| BRAF V600E | 0 | BRAF p.V640E | 137 |
| H3 K27M (H3-3A) | 0 | H3-3A p.K28M | 98 |

BRAF is numbered on the annotation transcript, which is 40 residues longer than the one the clinical name refers to. The histone change follows standard notation, which counts the initial methionine; the clinical name does not. An analyst who searches for either clinical name finds nothing.

## Identical variants recurring across unrelated tumor types

These identical protein changes appear in at least 20 cases spread over at least 10 diagnosis labels, in genes with no known hotspot. A real somatic hotspot tracks tumor type. A change that recurs regardless of tumor type is more likely a recurrent calling artifact or a germline variant left in the somatic file. **This issue was first raised by the AI agents in their audit notes, not by the authors.** It is offered for review by the Genomic Data Commons and CCDI, and has not been confirmed.

| Gene | Protein change | Cases | Diagnosis labels |
|---|---|---|---|
| C17orf80 | p.S281R | 128 | 45 |
| HLTF | p.Q898E | 83 | 43 |
| ZNF510 | p.Q248E | 51 | 23 |
| CD69 | p.L176Q | 44 | 19 |
| CD46 | p.K388N | 38 | 21 |
| TSPAN19 | p.D123N | 23 | 14 |
| CCDC168 | p.Q1530* | 21 | 14 |
| SLAMF7 | p.W184R | 21 | 15 |

Together these 8 variants account for 409 case-level calls. An enrichment analysis that does not remove them will report these genes as findings in whichever small group happens to carry a few.

## Flags for curator review

65 cases carry a non-specific label and a mutation that is characteristic of a specific entity. These are suggestions for review by CCDI curators and pathologists. They are not diagnoses. The full list is written to `curator_flags.csv` when the report is run locally; it is not published in this repository.

| Suggested review category | Flags |
|---|---|
| Diffuse midline glioma, H3 K27-altered | 23 |
| BRAF V600E-altered tumor (several entities) | 22 |
| WNT-pathway activated tumor | 8 |
| IDH-mutant glioma | 7 |
| Diffuse hemispheric glioma, H3 G34-mutant | 3 |
| Diffuse midline glioma (ACVR1 co-mutation) | 2 |
| Spindle cell/sclerosing rhabdomyosarcoma, MYOD1-mutant | 2 |
