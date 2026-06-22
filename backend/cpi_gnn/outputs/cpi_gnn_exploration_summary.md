# CPI / GNN Exploration Summary

Run time: 2026-06-01 16:17:42

## 1. Purpose

This notebook explores the CPI_prediction repository suggested for compound-protein interaction prediction. The purpose is to test whether the repository can be reproduced in Colab, whether GPU can be used, and whether the CPI model can generate machine learning outputs that may later be integrated with the MRDRP dashboard.

## 2. Repository and model type

- Repository: https://github.com/masashitsubaki/CPI_prediction
- Model direction: compound-protein interaction prediction.
- Compound input: SMILES converted into molecular graph features using RDKit.
- Protein input: amino acid sequence represented using n-gram features.
- Model structure: GNN-based compound encoder and CNN/attention-based protein encoder.
- Important note: this repository mainly uses 2D molecular graph representation from SMILES, not a full 3D coordinate-based GNN.

## 3. Environment

- PyTorch version: 2.11.0+cu128
- CUDA available: True
- GPU: Tesla T4

## 4. Compatibility patches applied

- RDKit installation was adapted for the current Colab Python environment by using the modern `rdkit` package instead of `rdkit-pypi`.
- `preprocess_data.py` was patched to save heterogeneous molecular graph objects as NumPy object arrays with `allow_pickle=True`.
- `run_training.py` was patched to load object arrays using `np.load(..., allow_pickle=True)`.
- A quick subset dataset was created to avoid running the original full 100-iteration training script during initial exploration.

## 5. Quick training setting

- Dataset: human_quick
- Quick subset size: 300 CPI samples
- Training mode: smoke test / feasibility run
- Iterations: 3 setting in shell script, resulting in 2 training epochs
- Purpose: verify that the repo can preprocess data, use GPU, train a model, and produce outputs.

## 6. Quick training AUC output

- AUC file: `/content/drive/MyDrive/UM_WQF7023/CPI_3D_GNN_Exploration/CPI_prediction/output/result/AUCs--human_quick--quick--radius2--ngram3--dim10--layer_gnn1--window11--layer_cnn1--layer_output1--lr1e-3--lr_decay0.5--decay_interval10--weight_decay1e-6--iteration3.txt`

|   Epoch |   Time(sec) |   Loss_train |   AUC_dev |   AUC_test |   Precision_test |   Recall_test |
|--------:|------------:|-------------:|----------:|-----------:|-----------------:|--------------:|
|       1 |     1.41091 |      163.984 |  0.76     |   0.75     |         0.736842 |         0.875 |
|       2 |     2.19278 |      146.837 |  0.786667 |   0.825893 |         0.823529 |         0.875 |

## 7. Quick evaluation metrics

|   accuracy |   precision |   recall |       f1 |      auc |   n_test |   positive_true_count |   positive_pred_count |
|-----------:|------------:|---------:|---------:|---------:|---------:|----------------------:|----------------------:|
|   0.833333 |    0.823529 |    0.875 | 0.848485 | 0.825893 |       30 |                    16 |                    17 |

## 8. Confusion matrix

|                          |   Pred_0_non_interaction |   Pred_1_interaction |
|:-------------------------|-------------------------:|---------------------:|
| Actual_0_non_interaction |                       11 |                    3 |
| Actual_1_interaction     |                        2 |                   14 |

## 9. Classification report

|                 |   precision |   recall |   f1-score |   support |
|:----------------|------------:|---------:|-----------:|----------:|
| non_interaction |    0.846154 | 0.785714 |   0.814815 | 14        |
| interaction     |    0.823529 | 0.875    |   0.848485 | 16        |
| accuracy        |    0.833333 | 0.833333 |   0.833333 |  0.833333 |
| macro avg       |    0.834842 | 0.830357 |   0.83165  | 30        |
| weighted avg    |    0.834087 | 0.833333 |   0.832772 | 30        |

## 10. Interpretation

The quick CPI model run successfully used GPU and generated AUC, precision, recall, confusion matrix, and classification report outputs. This confirms that the CPI_prediction repository can be adapted and executed in the current Colab environment. However, the current quick result should not be treated as a final benchmark because it uses only a small subset and very few training epochs.

## 11. Integration with MRDRP

The MR pipeline provides genetic evidence for exposure-outcome relationships, while the CPI module can provide molecular interaction prediction between Artesunate and candidate protein targets. The next development step is to prepare Artesunate SMILES and candidate protein sequences, then evaluate whether the trained or adapted CPI model can score Artesunate-protein interactions.

## 12. Next technical steps

- Retrieve and verify Artesunate SMILES from a reliable chemical database.
- Create a candidate protein target list relevant to Artesunate, SHBG/GDF15-related biology, or endometrial cancer pathways.
- Prepare protein sequences in FASTA / amino acid sequence format.
- Build a prediction input table with compound SMILES and protein sequences.
- Decide whether to use the current CPI model as a feasibility module or extend toward a true 3D GNN using molecular conformers and 3D coordinates.
- Add a CPI / Molecular Interaction Prediction page to the dashboard after prediction outputs are available.