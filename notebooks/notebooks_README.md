# notebooks/

P2-era Colab notebooks, kept here for anyone (including future developers of this project) who wants to see how the pipeline was built and run before it was migrated to a persistent Linux server, or who wants to understand/reproduce individual pieces of the MR and CPI/GNN backends outside the live dashboard.

## Files

### `Python_based_MR_drug_repurposing_pipeline.ipynb`
The original MR analysis notebook, used during early P2 development before the one-click "Run" button existed on the dashboard. Contains the R / rpy2 / TwoSampleMR / ieugwasr environment setup (including OpenGWAS JWT authentication) and the cells used to call `mr_pipeline.run_pipeline_for_analysis_set()` by hand for a given analysis set. Useful for understanding exactly what R environment and package versions the MR backend depends on, independent of the dashboard/server-deployment layer.

### `CPI_&_3D_GNN_exploration.ipynb`
The compound-protein interaction exploration notebook — builds and runs the GNN (compound) + CNN (protein) model described in `backend/CPI_3D_GNN_Exploration/`. This is where the UniProt sequence retrieval, the RDKit 3D conformer generation for Artesunate, model retraining with the real target pairs, and the final inference step actually happen. The dashboard's "CPI / GNN Exploration" page only *displays* the outputs this notebook produces.

### `WQF7023_MRDRP_Dashboard_Launcher.ipynb`
The Colab-based launcher used **before migrating to the current persistent Linux server deployment**. Installs Streamlit, starts the dashboard, and opens a Cloudflare quick tunnel to generate a temporary public link — this was the fastest way to test the dashboard or let someone else try it during active development, without needing a permanent server. Superseded by `deploy_dashboard.py` (in the repository root) for the current, persistent deployment, but kept here as a lightweight alternative if you ever need to spin the dashboard up quickly in a fresh Colab session instead.

## Why these are useful to a new developer

Together, these three notebooks show the project's logic in an easier-to-step-through, cell-by-cell form than the production `.py` files — useful for learning how the MR pipeline and the CPI/GNN exploration actually work end-to-end, or for reproducing a piece of it independently, before diving into `app.py`, `mr_pipeline.py`, and the rest of the deployed dashboard code.
