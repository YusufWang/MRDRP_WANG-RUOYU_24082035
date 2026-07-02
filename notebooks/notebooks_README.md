# Development Notebooks

This folder contains the original Google Colab notebooks used during the development, exploration, and testing stages of the P1 prototype. These notebooks represent the working process behind the deployed dashboard (`app.py`) in the repository root, and they are provided here for transparency and reproducibility.

The five notebooks correspond directly to Appendix B–F in the project report, and are listed below in the order of the development workflow rather than alphabetically, so that the overall pipeline logic is easier to follow.

| Notebook | Report Appendix | Stage |
|---|---|---|
| `GWAS_File_Download.ipynb` | Appendix F | Data collection |
| `Artesunate_related_candidate_collection.ipynb` | Appendix D | Early-stage GWAS file screening |
| `Python_based_MR_drug_repurposing_pipeline.ipynb` | Appendix C | MR backend, rsID mapping, LD clumping |
| `CPI___3D_GNN_exploration.ipynb` | Appendix E | CPI/GNN molecular exploration |
| `WQF7023_Targeted_Dashboard.ipynb` | Appendix B | Dashboard development and integration |

---

## 1. `GWAS_File_Download.ipynb`

**Purpose:** This notebook was used to download selected GWAS summary statistics files from the GWAS Catalog / EBI summary statistics FTP repository into the project's Google Drive folder structure, organised by exposure trait (IGF1, SHBG, ADIPOQ, GDF15) and outcome (endometrial cancer).

**Key content:** Google Drive mounting, target folder setup, and file download using the EBI FTP URL pattern.

---

## 2. `Artesunate_related_candidate_collection.ipynb`

**Purpose:** This notebook implements the earlier version of the GWAS file suitability screening logic. It scans the exposure and outcome folders, previews each file, and classifies it as *Suitable candidate*, *Needs adaptation*, or *Not suitable for current pipeline* based on the presence of core MR-related fields.

**Key content:** `inspect_columns()` — the original version of the field-detection and classification function. This logic was later carried into the dashboard (`WQF7023_Targeted_Dashboard.ipynb`) and the deployed `app.py`, with the classification categories refined into the five-status system described in Table 5.2 of the report.

---

## 3. `Python_based_MR_drug_repurposing_pipeline.ipynb`

**Purpose:** This is the main MR backend notebook. It covers the full workflow from environment setup to clumped MR results, including R/Python integration via `rpy2` and `TwoSampleMR`.

**Key content:**
- Environment setup (R base, `TwoSampleMR`, `ieugwasr`)
- GWAS file standardisation and significant variant selection
- Coordinate-based MR analysis (without clumping)
- Multi-outcome comparison
- rsID mapping using the Ensembl REST API (Cell 23.2)
- LD clumping via `TwoSampleMR::clump_data()`, using `clump_kb = 10000`, `clump_r2 = 0.001`, `pop = "EUR"` (Cell 23.5)
- Combined and ranked clumped MR results

**Note:** LD clumping requires a valid OpenGWAS JWT token (Cell 23.5A), which must be set as an environment variable before running Cell 23.5.

---

## 4. `CPI___3D_GNN_exploration.ipynb`

**Purpose:** This notebook explores compound-protein interaction (CPI) prediction as a complementary evidence layer to the MR analysis, examining whether Artesunate may interact with candidate protein targets (SHBG, GDF15, IGF1, ADIPOQ).

**Key content:**
- Clones and adapts the external repository [`masashitsubaki/CPI_prediction`](https://github.com/masashitsubaki/CPI_prediction)
- Patches `preprocess_data.py` and `run_training.py` for compatibility with current NumPy and Python versions
- Builds a quick subset dataset and runs GPU-based quick training as a feasibility test
- Generates evaluation metrics (AUC, precision, recall, accuracy, F1-score) and a confusion matrix

**Note:** The model architecture (`CompoundProteinInteractionPrediction`) is adapted from the cloned repository above, not built from scratch. This notebook's contribution is environment adaptation, quick-training validation, and integration into the dashboard — not the underlying model design.

---

## 5. `WQF7023_Targeted_Dashboard.ipynb`

**Purpose:** This notebook was used to develop and test the Streamlit dashboard prior to deployment. It integrates the file screening logic, analysis set selection, backend MR result display, and CPI/GNN output display into a single multi-page Streamlit application.

**Key content:**
- Six dashboard pages: Home, Targeted File Screening, Analysis Set Selection, Backend MR Results, MR Pipeline + LD Clumping, CPI / GNN Exploration
- Refined version of `inspect_columns()`, matching the logic later deployed in `app.py`
- Screening record and analysis set record read/write functions (CSV-based storage)

---

## Environment Notes

- Notebooks 3 and 4 require a GPU runtime (Colab: **Runtime > Change runtime type > T4 GPU**).
- Notebook 3 requires R and several R packages (`TwoSampleMR`, `ieugwasr`) installed via `apt-get` and `rpy2`, in addition to a valid OpenGWAS JWT token for the LD clumping step.
- All notebooks assume the project folder structure under `/content/drive/MyDrive/UM_WQF7023/MRDRP-main/`, consistent with the folder layout in the repository root (`exposures/`, `outcome/`).

## Relationship to the Deployed Dashboard

The deployed `app.py` in the repository root is the production version of the logic developed and tested in `WQF7023_Targeted_Dashboard.ipynb`. The backend MR results and CPI/GNN outputs shown in the deployed dashboard were generated using the pipelines in notebooks 3 and 4, then exported as lightweight CSV/summary files for online demonstration.
