# MRDRP Artesunate Drug Repurposing Dashboard

This repository contains the source code and lightweight deployment files for the **MRDRP Artesunate Drug Repurposing Dashboard** developed for the WQF7023 Master of Artificial Intelligence project.

The project focuses on the integration of **Mendelian Randomization (MR)** and **compound-protein interaction (CPI) / graph neural network (GNN) exploration** into a drug repurposing workflow. The current prototype uses Artesunate-related biological exposure candidates and endometrial cancer as the target disease outcome.

## Deployed Dashboard

The deployed Streamlit dashboard can be accessed here:

https://mrdrpwang-ruoyu24082035-cojen6rp4mgqnb2fvydgo6.streamlit.app/

## Project Overview

The purpose of this project is to develop a prototype decision-support dashboard for drug repurposing. The system is designed to combine genetic evidence and molecular interaction evidence in one workflow.

In the current version, the MR module focuses on selected Artesunate-related exposure candidates:

- IGF1
- SHBG
- ADIPOQ
- GDF15

The target outcome is:

- Endometrial cancer

The dashboard allows users to inspect GWAS summary statistics files, check whether they contain the required MR-related columns, prepare analysis sets, review backend MR results, and view CPI/GNN exploration outputs.

## Main Features

### 1. Targeted File Screening

The dashboard scans GWAS files stored under the `exposures/` and `outcome/` folders. It checks whether each file contains important fields, including:

- variant identifier
- chromosome
- position
- effect allele
- other allele
- beta or odds ratio
- standard error
- effect allele frequency
- p-value
- sample size

The page classifies each file as a suitable candidate, a file requiring adaptation, or a file not suitable for the current pipeline.

### 2. Analysis Set Selection

The dashboard supports a multiple-exposure and one-outcome analysis setting. The current analysis set includes IGF1, SHBG, ADIPOQ, and GDF15 as exposures, with endometrial cancer as the outcome.

The page checks:

- whether all required exposure traits are selected
- whether the selected files share the same genome build
- whether any file requires adaptation
- whether the analysis set is ready for backend MR processing

### 3. Backend MR Results

The backend MR module demonstrates the feasibility of using GWAS summary statistics for MR-based drug repurposing analysis. The current workflow includes:

- GWAS preprocessing
- significant variant selection
- rsID mapping
- LD clumping
- harmonisation
- MR result generation
- multi-outcome comparison

The deployed version includes lightweight result tables and summary reports so that the dashboard can be demonstrated online.

### 4. MR Pipeline and LD Clumping

This module displays the improved MR pipeline after adding rsID mapping and LD clumping. This step helps to make the MR analysis more methodologically rigorous by reducing correlated genetic instruments.

The current results should be interpreted as prototype evidence rather than final clinical or biological conclusions.

### 5. CPI / GNN Exploration

The CPI/GNN module explores how compound-protein interaction prediction can be integrated into the drug repurposing dashboard. The current exploration is based on a CPI prediction repository and demonstrates:

- preprocessing compatibility adjustment
- quick subset training
- model evaluation
- candidate protein target preparation
- dashboard integration of CPI/GNN output files

This module is a feasibility exploration. It is not yet a final Artesunate-protein prediction system.

## Repository Structure

```text
MRDRP_WANG-RUOYU_24082035/
├── app.py
├── requirements.txt
├── README.md
├── LICENSE
├── MR-Icon.png
├── MRdata.py
├── MRanalysis.py
├── analysis_set_record.csv
├── artesunate_file_screening_record.csv
│
├── exposures/
│   ├── IGF1/
│   ├── SHBG/
│   ├── ADIPOQ/
│   └── GDF15/
│
├── outcome/
│   └── endometrial_cancer/
│
├── backend_work/
│   └── mr_outputs/
│       └── summary/
│
└── backend/
    └── cpi_gnn/
        ├── outputs/
        └── CPI_prediction/
            └── output/
                └── evaluation/
```

## Deployment Notes

This repository is prepared for Streamlit Cloud deployment. The deployed version uses small demonstration GWAS files and lightweight backend output files because full GWAS summary statistics files are too large for GitHub deployment.

The full GWAS data processing and backend experiments were performed in Google Colab. Large raw GWAS summary statistics files are not included in this repository.

## Local Installation

To run the dashboard locally, install the required packages:

```bash
pip install -r requirements.txt
```

Then start the Streamlit app:

```bash
streamlit run app.py
```

## Data Note

The deployed dashboard uses sampled or lightweight files to demonstrate the workflow. These files preserve the structure required for file screening and dashboard display. However, formal MR analysis should use full GWAS summary statistics files in the backend environment.

## Current Limitations

The current version is a prototype and has several limitations:

- Full GWAS summary statistics files are not included in the GitHub repository.
- The deployed dashboard uses lightweight demonstration files for online display.
- The CPI/GNN module is a feasibility exploration and not a final molecular prediction benchmark.
- The MR results should not be interpreted as final clinical evidence.
- Future work is needed to connect the dashboard to the GWAS Catalog API and support user-driven dataset selection.

## Future Work

Future development may include:

- GWAS Catalog API integration
- dynamic exposure and outcome search
- automated GWAS suitability checking
- automated backend MR execution
- improved CPI/GNN prediction for Artesunate-protein pairs
- pharmacist-facing interpretation layer
- stable server deployment

## Project Context

This project was developed as part of the WQF7023 Master of Artificial Intelligence project. It aims to demonstrate how MR-based genetic evidence and CPI/GNN-based molecular interaction evidence can be integrated into a drug repurposing dashboard.

## Author

Wang Ruoyu  
Master of Artificial Intelligence  
Universiti Malaya

## Acknowledgement

This project refers to the MRDRP pipeline structure and CPI/GNN-related repositories as technical foundations. The current repository adapts and extends these ideas into a targeted Artesunate drug repurposing dashboard prototype.
