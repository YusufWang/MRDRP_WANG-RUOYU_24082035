# MRDRP — Mendelian Randomization Drug Repurposing Dashboard

**A Streamlit dashboard integrating GWAS Catalog search, automated Mendelian Randomization (MR) analysis, and compound-protein interaction (CPI/GNN) exploration for drug repurposing research.**

Developed for the WQF7023 AI Research Project, Master of Artificial Intelligence, Universiti Malaya, under the supervision of Prof. CK Loo.

**Case study**: Artesunate repurposing for endometrial cancer, using IGF1, SHBG, ADIPOQ, and GDF15 as candidate biological exposures.

---

## Live Dashboard

**[https://measured-hazards-cindy-revised.trycloudflare.com/)**

This is a live, working deployment on a university lab server — not a static demo. All features described below are fully functional at this link, including live GWAS Catalog search, file screening, and one-click MR analysis with real-time progress.

*Note: this is a tunnel URL and may change if the server deployment is restarted. If the link above doesn't load, please contact the author for a current link.*

---

## What This Project Is

MRDRP is a decision-support tool for researchers doing MR-based drug repurposing analysis: given a candidate drug's biological targets (exposures) and a disease of interest (outcome), it helps find, prepare, and analyse the genetic evidence linking them, without requiring the user to manually navigate GWAS Catalog's website, write file-parsing code, or hand-run an R/TwoSampleMR pipeline in a notebook.

This repository represents the **P2 phase** of the project. The original P1 phase (developed earlier in the same degree program) was a fixed case-study pipeline — hardcoded to the same four exposures and one outcome, with files downloaded and screened by hand. P2 rebuilt this into a general-purpose, self-contained dashboard: any exposure and outcome combination can be searched for, fetched, screened, and analysed directly through the web interface.

---

## What's Implemented

### GWAS Catalog Search
The centrepiece of P2. Talks to **two independent EBI services**:
- **Main GWAS Catalog REST API v2** — keyword search for traits, then studies for a chosen trait
- **Summary Statistics API** — pulls genome-wide-significant variants for a chosen study directly, without downloading a full raw file first

Key capabilities:
- **Automated genome build detection**, in order of reliability: (1) presence of an EBI-harmonised file (guaranteed GRCh38), (2) a build tag in the filename, (3) a `-meta.yaml` sidecar file, (4) if none of these resolve it, an offered **liftover** (GRCh37→GRCh38 via R's `rtracklayer::liftOver()`, called through rpy2)
- **Role-aware filtering**: exposure files are filtered to genome-wide-significant variants (p < threshold); outcome files are saved *unfiltered*, since MR needs to check the outcome's values at the exposure's specific variant positions regardless of the outcome's own significance there
- **Gzip-compressed storage** (`.csv.gz`) for all saved files — typically 8x+ smaller than plain CSV, with no changes needed on the reading side
- **Synonym/full-name search expansion** (e.g. "IGF1" also searches "insulin-like growth factor 1"), plus a fallback query to EBI's OLS4 ontology service, and ranking that prioritises "measurement"-type traits over disease-association traits for biomarker searches
- **Relaxed, more accurate file-suitability screening** — standard error and p-value can each be derived from the other plus the effect size (Wald-test relationship), so a file missing only one of them is no longer auto-rejected
- **Layered error handling** — rate limits, server errors, and malformed responses are caught and explained clearly instead of crashing the page
- **Emergency fallback tools** for when EBI's Main API v2 is degraded (this happens occasionally): manual EFO ID / GCST accession entry, a "skip metadata lookup" bypass that goes straight to the Summary Statistics API / FTP archive (independent services, typically unaffected), and a last-resort bulk keyword search against EBI's full studies metadata export

### Targeted File Screening
Batch-scans saved files, checks for all fields required by the MR pipeline, flags each as suitable / needs adaptation / not suitable. Delete removes the underlying file, not just the tracking record. Includes a direct download button and file size/row count display (useful for spotting narrow-coverage files, e.g. exome-restricted studies masquerading as genome-wide).

### Analysis Set Selection
Freely combine any number of exposure and outcome files into a named analysis set (not limited to a fixed exposure/outcome count). A set can include multiple outcome files as a hedge against any single outcome study having inadequate coverage. Existing sets can be edited in place.

### Backend MR Results — one-click MR analysis
Select a saved analysis set, paste an OpenGWAS API token, click **Run**. The analysis launches as a genuine detached background process on the server — it keeps running even if the browser is closed or the dashboard itself restarts, as long as the server stays up. A live-updating progress bar shows the current percentage and step (e.g. "Exposure 2/3: mapping rsIDs via Ensembl (23/47)"). Once finished, results (LD clumping summary, MR run summary, and combined effect estimates across methods) are displayed automatically.

Backend pipeline: standardises heterogeneous GWAS file formats → filters to significant variants → maps to rsIDs (Ensembl, with a fast path for files that already carry rsIDs) → LD-clumps via `TwoSampleMR::clump_data()` → matches outcome data by genomic position across a three-tier fallback strategy → runs MR (IVW, MR-Egger, weighted median, weighted mode, simple mode) via `TwoSampleMR::mr()`. Results are cached per exposure/threshold combination so re-running an unchanged analysis set doesn't repeat the slower steps.

### CPI/GNN Exploration
A separate, exploratory line of evidence: a GNN (compound) + CNN (protein) model estimating Artesunate's interaction probability against the four candidate targets. Uses real UniProt (Swiss-Prot) sequences for the proteins and a real RDKit-generated 3D conformer for Artesunate (though the model's own encoder is still 2D-graph-based at this stage — the 3D data is prepared but not yet consumed by the architecture). Retrained with these four real pairs held out for inference only. Presented with an explicit caveat that this is a small-sample, no-negative-control exploratory signal, not a validated biological prediction.

---

## How to Use the Dashboard

A typical new analysis, start to finish:

1. **GWAS Catalog Search** — search for your exposure trait, list its studies, preview and save the significant variants as an `exposure`. Repeat for your outcome trait, saving it as an `outcome` (note: outcome files are saved unfiltered by design — this is expected).
   - *If Main API v2 search isn't responding* (an occasional EBI-side issue, not a bug here): use the "Already know the EFO ID or GCST accession?" expander to search directly by accession, or "Skip metadata lookup, use this accession directly" to bypass Main API v2 entirely, or the "Emergency bulk keyword search" as a last resort. All three are visible on the same page.
2. **Targeted File Screening** — run a batch scan and confirm your saved files are flagged as usable.
3. **Analysis Set Selection** — group your exposure(s) and outcome(s) into a named set.
4. **Backend MR Results** — pick your set, paste an OpenGWAS token (get one at [api.opengwas.io](https://api.opengwas.io/) — there's a link and short explanation right next to the token field on the page), click **Run MR analysis for this set**, and watch the live progress. Results appear on the same page once finished.

When reading results: check the instrument count behind each estimate (very few SNPs means MR-Egger/weighted median aren't statistically meaningful — the clumping summary flags this), and treat a bare p<0.05 with appropriate caution, especially if MR-Egger disagrees sharply with the simpler methods.

---

## For Developers: Extending or Adapting This Project

If you're building something similar — an MR pipeline dashboard for a different disease/compound, or just want to reuse pieces of this — here's how the codebase is organised:

| File | Role |
|---|---|
| `app.py` | The Streamlit dashboard itself — all pages, all UI. Pure Python; does **not** import R/rpy2 directly (see Architecture note below). |
| `gwas_catalog_client.py` | Client for EBI's Main REST API v2 and Summary Statistics API. Includes the trait synonym table and OLS4 fallback search. |
| `gwas_catalog_ftp.py` | Client for EBI's FTP archive — the fallback data source, and the route used by the outcome-fetching logic in the MR pipeline. |
| `mr_pipeline.py` | The MR analysis engine: standardisation, significance filtering, rsID mapping, LD clumping, outcome matching, and the TwoSampleMR calls themselves (via rpy2). Designed to be run either from a notebook cell or by the launcher script below. |
| `run_mr_analysis_for_set.py` | Background-process launcher invoked by the dashboard's "Run" button. Reads the OpenGWAS token from an environment variable, calls `mr_pipeline.run_pipeline_for_analysis_set()` with a progress callback, and writes progress/results to disk for the dashboard to poll. |
| `deploy_dashboard.py` | Sets up the full deployment: Streamlit itself, a branded HTML wrapper (header/logo/embedded iframe), and two Cloudflare tunnels — all inside `tmux` sessions so they survive terminal/SSH disconnects. |
| `fix_screening_record_paths.py` | One-off utility for repairing absolute file paths in the screening record after moving the project between environments (e.g. Colab → a different server) — a good example of the kind of environment-specific gotcha to watch for if you deploy this elsewhere. |

**Architecture note — why R lives in a separate process from the dashboard**: `app.py` is pure Python and never imports rpy2. The MR analysis (which genuinely needs R/TwoSampleMR/ieugwasr) always runs as a **separate process** — either a notebook cell during development, or the background subprocess launched by `run_mr_analysis_for_set.py` in production. This keeps the dashboard itself lightweight and R-free, and is also *why* the one-click "Run" button can survive the browser being closed: the analysis is a real OS-level process, not something tied to the Streamlit session.

**If you want to adapt this for a different case study**: the exposure/outcome trait names aren't hardcoded anywhere in the P2 code — everything is driven by whatever you search for and save through the GWAS Catalog Search page, then group in Analysis Set Selection. You shouldn't need to touch the Python files at all to point this at a different drug/disease combination.

---

## Limitations of This Repository

This repository is provided for **code review and reproducibility of the logic**, not as a one-click "clone and run" package. A few things to be aware of:

- **The R/MR backend cannot run on GitHub or a typical free hosting tier.** `mr_pipeline.py` depends on a working R installation with `TwoSampleMR` and `ieugwasr` compiled and available, bridged into Python via `rpy2`. Getting these R packages compiled and linked correctly (see the commit history / thesis report for the debugging involved) is itself a non-trivial setup step that assumes a persistent server, not a container spun up fresh on every push. Streamlit Community Cloud and similar free-tier services do not reliably support this.
- **Large data files are intentionally excluded.** GWAS summary statistics files (the `exposures/`, `outcome/`, and `backend_work/` folders in the working deployment) are excluded via `.gitignore` — they range from a few MB to multiple GB, are regenerated on demand by the dashboard itself from EBI's own servers, and are not appropriate to version-control or redistribute from this repository.
- **No OpenGWAS token is stored anywhere in this repository.** The token is entered by the user in the browser at analysis time and passed to the background process via an environment variable — it is never written to disk or committed.
- **The live link above is the actual system.** If you want to see this project working end-to-end rather than reading the source, that link is the right place to look — not an attempt to run this repository locally.

If you do want to run this yourself, you'll need: Python 3.12+ with the packages in `requirements.txt`, a working R 4.x installation with `TwoSampleMR` and `ieugwasr` installed, and an [OpenGWAS](https://api.opengwas.io/) account for a JWT token.

---

## Project History

- **P1**: fixed case-study pipeline (IGF1/SHBG/ADIPOQ/GDF15 → endometrial cancer), manual file preparation, notebook-run MR analysis.
- **P2** (this repository's current state): general-purpose GWAS Catalog search and screening, arbitrary exposure/outcome analysis sets, one-click background MR analysis with live progress, CPI/GNN exploration with real protein/compound data, and deployment to a persistent, publicly-reachable server.

---

## Author

Wang Ruoyu (24082035)
Master of Artificial Intelligence, Universiti Malaya
Supervisor: Prof. CK Loo
