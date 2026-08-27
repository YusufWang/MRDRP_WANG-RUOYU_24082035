# CPI_3D_GNN_Exploration

Exploratory compound-protein interaction (CPI) evidence layer for the MRDRP project — a GNN (compound) + CNN (protein) model estimating whether Artesunate is likely to interact with each of the four MR candidate targets (SHBG, GDF15, IGF1, ADIPOQ). This is a secondary, supplementary line of evidence alongside the MR causal analysis, not a replacement for it.

## Folder contents

| Path | Contents |
|---|---|
| `CPI_prediction/` | The underlying CPI model repository (compound-graph + protein-sequence encoders, training/inference code). |
| `outputs/` | Generated artifacts consumed by the dashboard's "CPI / GNN Exploration" page: protein sequences, the Artesunate SMILES/3D conformer files, retraining logs, and the final Artesunate-target inference results. |

## What changed in P2

P1 had this pipeline running end-to-end on a generic benchmark subset, but with **placeholder (empty) protein sequences** for the four targets and only a **2D SMILES** representation for Artesunate. P2 closed both gaps at the data level:

- **Real protein sequences**: SHBG, GDF15, IGF1, and ADIPOQ now use verified, reviewed sequences retrieved from UniProt (Swiss-Prot), replacing the P1 placeholders.
- **Real 3D structure for Artesunate**: a genuine 3D conformer was generated with RDKit (ETKDGv3 embedding + MMFF94 energy minimisation), replacing the 2D-SMILES-only representation.
- **Retraining with real data**: since the original model's vocabulary had never seen Artesunate or these four real proteins, it would fail on out-of-vocabulary substructures at inference time. The model was retrained with these four real pairs encoded into the vocabulary, with the four pairs strictly held out of train/validation/test and used only for final inference. Benchmark test AUC after retraining: **0.9643**.
- **Real inference results**: GDF15 (0.810, interaction), SHBG (0.686, interaction), ADIPOQ (0.261, non-interaction), IGF1 (0.059, non-interaction).

**What did *not* change**: the model's own graph encoder is still 2D. The 3D conformer data is generated and available, but is not yet consumed by the model architecture itself — that would require a genuine 3D-aware GNN, which is future work, not something claimed as done here.

## How to read these results

This is an **exploratory, small-sample signal** — four compound-protein pairs, no negative controls, and no independently known ground-truth interaction label for Artesunate itself. Treat the interaction probabilities as a supplementary, model-derived hint to sit alongside the MR evidence, not as a validated biological prediction. The dashboard's own "Artesunate-target prediction (P2)" tab carries this same caveat directly next to the results table.
