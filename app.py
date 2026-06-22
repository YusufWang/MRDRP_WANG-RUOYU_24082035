
import os
import re
import shutil
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


# =========================================================
# Page config
# =========================================================
st.set_page_config(
    page_title="MRDRP Targeted Dashboard",
    page_icon="🧬",
    layout="wide"
)


# =========================================================
# Custom style
# =========================================================

st.markdown(
    """
    <style>
    :root {
        --brand: #1F6F5F;
        --brand-2: #2B8A74;
        --bg: #DDE4E1;
        --bg-soft: #CCD6D1;
        --card: #F7F9F8;
        --sidebar: #D7DFDB;
        --text: #24312D;
        --muted: #5E6A66;
        --border: #BFCBC6;
        --shadow: 0 4px 16px rgba(31, 111, 95, 0.08);
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --brand: #38A38C;
            --brand-2: #4DB7A0;
            --bg: #1A1D20;
            --bg-soft: #24282C;
            --card: #30363B;
            --sidebar: #22262A;
            --text: #F2F5F4;
            --muted: #A8B2AE;
            --border: #4A5359;
            --shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        }
    }

    html, body, [data-testid="stAppViewContainer"], .stApp {
        background: var(--bg) !important;
        color: var(--text) !important;
    }

    header[data-testid="stHeader"] {
        background: var(--bg) !important;
        border-bottom: none !important;
        box-shadow: none !important;
    }

    div[data-testid="stToolbar"] {
        background: transparent !important;
    }

    .block-container {
        padding-top: 1.1rem !important;
        padding-bottom: 2rem !important;
    }

    section[data-testid="stSidebar"] {
        background: var(--sidebar) !important;
        border-right: 1px solid var(--border) !important;
    }

    section[data-testid="stSidebar"] * {
        color: var(--text) !important;
    }

    h1, h2, h3 {
        color: var(--brand) !important;
        font-weight: 700 !important;
    }

    p, label, span, div {
        color: var(--text);
    }

    div[data-testid="stMetric"] {
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 16px !important;
        padding: 14px !important;
        box-shadow: var(--shadow) !important;
    }

    div[data-testid="stMetric"] * {
        color: var(--text) !important;
    }

    [data-testid="stExpander"] {
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        overflow: hidden !important;
    }

    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary * {
        background: var(--bg-soft) !important;
        color: var(--text) !important;
    }

    [data-testid="stExpander"] * {
        color: var(--text) !important;
    }

    pre, code, [data-testid="stCodeBlock"] {
        background: var(--card) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
    }

    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea {
        background: var(--card) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
    }

    .stTextInput label,
    .stTextArea label,
    .stNumberInput label,
    .stSelectbox label,
    .stMultiSelect label,
    .stSlider label {
        color: var(--text) !important;
    }

    div[data-baseweb="select"] > div {
        background: var(--card) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
    }

    div[data-baseweb="select"] * {
        color: var(--text) !important;
    }

    div[data-baseweb="popover"],
    div[data-baseweb="menu"] {
        background: var(--card) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }

    div[data-baseweb="popover"] *,
    div[data-baseweb="menu"] * {
        color: var(--text) !important;
    }

    [data-testid="stToolbar"] button,
    [data-testid="stToolbar"] * {
        color: var(--text) !important;
    }

    [role="menu"],
    [role="menu"] * {
        background: var(--card) !important;
        color: var(--text) !important;
    }

    [role="menuitem"],
    [role="menuitem"] * {
        color: var(--text) !important;
    }

    div[data-testid="stDataFrame"] {
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        padding: 6px !important;
    }

    table,
    .stMarkdown table {
        color: var(--text) !important;
        background: var(--card) !important;
        border-collapse: collapse !important;
    }

    thead tr th,
    .stMarkdown thead tr th {
        background: var(--bg-soft) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }

    tbody tr td,
    .stMarkdown tbody tr td {
        color: var(--text) !important;
        background: transparent !important;
        border: 1px solid var(--border) !important;
    }

    .stMarkdown tbody tr:nth-child(even) td {
        background: var(--bg-soft) !important;
    }

    [data-testid="stDataFrame"] * {
        color: var(--text) !important;
    }

    .stAlert {
        border-radius: 12px !important;
    }

    .stButton > button {
        background: var(--brand) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.55rem 1rem !important;
    }

    .stButton > button:hover {
        background: var(--brand-2) !important;
        color: white !important;
    }

    .nav-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 22px;
        box-shadow: var(--shadow);
        min-height: 175px;
        margin-bottom: 12px;
    }

    .nav-card h3 {
        margin-top: 0px;
        color: var(--brand) !important;
    }

    .small-note {
        color: var(--muted);
        font-size: 0.95rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)



# =========================================================
# Paths
# =========================================================
COLAB_PROJECT_ROOT = Path("/content/drive/MyDrive/UM_WQF7023/MRDRP-main")

if COLAB_PROJECT_ROOT.exists():
    PROJECT_ROOT = COLAB_PROJECT_ROOT
else:
    PROJECT_ROOT = Path(__file__).parent
EXPOSURES_DIR = PROJECT_ROOT / "exposures"
OUTCOME_DIR = PROJECT_ROOT / "outcome"

TARGET_RECORD_FILE = PROJECT_ROOT / "artesunate_file_screening_record.csv"
ANALYSIS_SET_RECORD_FILE = PROJECT_ROOT / "analysis_set_record.csv"


# =========================================================
# CPI / GNN exploration output paths
# =========================================================
COLAB_CPI_ROOT = PROJECT_ROOT.parent / "CPI_3D_GNN_Exploration"
LOCAL_CPI_ROOT = PROJECT_ROOT / "backend" / "cpi_gnn"

if COLAB_CPI_ROOT.exists():
    CPI_ROOT = COLAB_CPI_ROOT
else:
    CPI_ROOT = LOCAL_CPI_ROOT
CPI_REPO_ROOT = CPI_ROOT / "CPI_prediction"
CPI_OUTPUT_ROOT = CPI_ROOT / "outputs"
CPI_REPO_OUTPUT_ROOT = CPI_REPO_ROOT / "output"

CPI_EXPLORATION_STATUS_FILE = CPI_OUTPUT_ROOT / "cpi_exploration_output_status.csv"
CPI_EXPLORATION_SUMMARY_FILE = CPI_OUTPUT_ROOT / "cpi_gnn_exploration_summary.md"
CPI_QUICK_TRAINING_LOG_FILE = CPI_OUTPUT_ROOT / "run_training_quick_log.txt"
CPI_QUICK_EVALUATION_LOG_FILE = CPI_OUTPUT_ROOT / "quick_evaluation_log.txt"

CPI_EVALUATION_DIR = CPI_REPO_OUTPUT_ROOT / "evaluation"
CPI_QUICK_EVALUATION_METRICS_FILE = CPI_EVALUATION_DIR / "quick_evaluation_metrics.csv"
CPI_QUICK_CONFUSION_MATRIX_FILE = CPI_EVALUATION_DIR / "quick_confusion_matrix.csv"
CPI_QUICK_CLASSIFICATION_REPORT_FILE = CPI_EVALUATION_DIR / "quick_classification_report.csv"
CPI_QUICK_TEST_PREDICTIONS_FILE = CPI_EVALUATION_DIR / "quick_test_predictions.csv"

CPI_ARTESUNATE_SMILES_FILE = CPI_OUTPUT_ROOT / "artesunate_smiles_pubchem.csv"
CPI_CANDIDATE_TARGET_TEMPLATE_FILE = CPI_OUTPUT_ROOT / "candidate_protein_target_template.csv"

# Global counter for CPI download buttons.
# This prevents duplicate Streamlit keys when the same CPI file is shown in multiple tabs.
CPI_DOWNLOAD_BUTTON_COUNTER = 0

def make_unique_cpi_download_key(prefix: str, label: str, file_name: str):
    global CPI_DOWNLOAD_BUTTON_COUNTER
    CPI_DOWNLOAD_BUTTON_COUNTER += 1
    return f"{prefix}_{CPI_DOWNLOAD_BUTTON_COUNTER}_{file_name}_{label}"



# Global counter for Streamlit download buttons.
# This prevents duplicate keys when the same file is shown in multiple tabs.
DOWNLOAD_BUTTON_COUNTER = 0

def make_unique_download_key(prefix: str, label: str, file_name: str):
    global DOWNLOAD_BUTTON_COUNTER
    DOWNLOAD_BUTTON_COUNTER += 1
    raw_key = f"{prefix}_{DOWNLOAD_BUTTON_COUNTER}_{label}_{file_name}"
    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()


BACKEND_ROOT = PROJECT_ROOT / "backend_work"
MR_OUTPUT_ROOT = BACKEND_ROOT / "mr_outputs"
MR_SUMMARY_DIR = MR_OUTPUT_ROOT / "summary"

BACKEND_STATUS_REPORT_FILE = MR_SUMMARY_DIR / "backend_mr_status_report.md"
MULTI_OUTCOME_REPORT_FILE = MR_SUMMARY_DIR / "multi_outcome_backend_mr_comparison_report.md"

SIGNIFICANT_VARIANT_QC_FILE = MR_SUMMARY_DIR / "significant_variant_qc.csv"
SNP_OVERLAP_FILE = MR_SUMMARY_DIR / "exposure_outcome_snp_overlap.csv"
COORDINATE_MR_RUN_SUMMARY_FILE = MR_SUMMARY_DIR / "coordinate_based_mr_run_summary.csv"
COORDINATE_COMBINED_MR_RESULTS_FILE = MR_SUMMARY_DIR / "coordinate_based_combined_mr_results.csv"

MULTI_OUTCOME_PREPARE_SUMMARY_FILE = MR_SUMMARY_DIR / "multi_outcome_prepare_summary.csv"
MULTI_OUTCOME_SNP_OVERLAP_FILE = MR_SUMMARY_DIR / "multi_outcome_snp_overlap.csv"
MULTI_OUTCOME_MR_RUN_SUMMARY_FILE = MR_SUMMARY_DIR / "multi_outcome_mr_run_summary.csv"
MULTI_OUTCOME_COMBINED_MR_RESULTS_FILE = MR_SUMMARY_DIR / "multi_outcome_combined_mr_results.csv"
MULTI_OUTCOME_CANDIDATES_FILE = MR_SUMMARY_DIR / "multi_outcome_analysis_sets.csv"
TOP_OUTCOME_CANDIDATES_FILE = MR_SUMMARY_DIR / "top_outcome_candidates_for_comparison.csv"

RSID_MAPPING_SUMMARY_FILE = MR_SUMMARY_DIR / "rsid_mapping_summary.csv"
LD_CLUMPING_INPUT_SUMMARY_FILE = MR_SUMMARY_DIR / "ld_clumping_input_summary.csv"
LD_CLUMPING_SUMMARY_FILE = MR_SUMMARY_DIR / "ld_clumping_summary.csv"
MR_READY_CLUMPED_EXPOSURE_SUMMARY_FILE = MR_SUMMARY_DIR / "mr_ready_clumped_exposure_summary.csv"
CLUMPED_MULTI_OUTCOME_SNP_OVERLAP_FILE = MR_SUMMARY_DIR / "clumped_multi_outcome_snp_overlap.csv"
CLUMPED_MULTI_OUTCOME_MR_RUN_SUMMARY_FILE = MR_SUMMARY_DIR / "clumped_multi_outcome_mr_run_summary.csv"
CLUMPED_MULTI_OUTCOME_COMBINED_MR_RESULTS_FILE = MR_SUMMARY_DIR / "clumped_multi_outcome_combined_mr_results.csv"
LD_CLUMPING_IMPROVEMENT_REPORT_FILE = MR_SUMMARY_DIR / "ld_clumping_improvement_report.md"



EXPOSURES_DIR.mkdir(parents=True, exist_ok=True)
OUTCOME_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# File helpers
# =========================================================
def infer_sep(file_name: str):
    if file_name.endswith(".csv") or file_name.endswith(".csv.gz"):
        return ","
    return "\t"


def infer_compression(file_name: str):
    if file_name.endswith(".gz"):
        return "gzip"
    return None


def is_supported_file(file_name: str):
    return (
        file_name.endswith(".tsv.gz")
        or file_name.endswith(".tsv")
        or file_name.endswith(".csv.gz")
        or file_name.endswith(".csv")
    )


def strip_extension(file_name: str):
    return (
        file_name
        .replace(".tsv.gz", "")
        .replace(".tsv", "")
        .replace(".csv.gz", "")
        .replace(".csv", "")
    )


def safe_widget_key(text: str):
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(text))


def read_preview_safely(file_path: Path, nrows: int = 5):
    sep = infer_sep(file_path.name)
    compression = infer_compression(file_path.name)

    try:
        return pd.read_csv(file_path, sep=sep, compression=compression, nrows=nrows)
    except OSError:
        local_path = Path("/content") / file_path.name
        shutil.copy2(file_path, local_path)
        return pd.read_csv(local_path, sep=sep, compression=compression, nrows=nrows)


def get_build_from_filename(file_name: str):
    lower = file_name.lower()
    if "grch37" in lower:
        return "GRCh37"
    if "grch38" in lower:
        return "GRCh38"
    return "Unknown"


def list_role_files(base_dir: Path, role: str):
    records = []

    if not base_dir.exists():
        return records

    for trait_folder in sorted(base_dir.iterdir()):
        if not trait_folder.is_dir():
            continue

        trait_name = trait_folder.name

        for file_path in sorted(trait_folder.iterdir()):
            if file_path.is_file() and is_supported_file(file_path.name):
                records.append({
                    "file_name": file_path.name,
                    "file_path": str(file_path),
                    "trait": trait_name,
                    "role": role
                })

    return records


def list_all_target_files():
    exposure_files = list_role_files(EXPOSURES_DIR, "exposure")
    outcome_files = list_role_files(OUTCOME_DIR, "outcome")
    return exposure_files + outcome_files


# =========================================================
# Column inspection logic
# =========================================================
def inspect_columns(columns):
    expected_groups = {
        "variant_identifier": ["rsid", "SNP", "variant_id", "hm_rsid", "rs_number", "variant"],
        "chromosome": ["chromosome", "chrom", "CHR", "chr"],
        "position": ["base_pair_location", "position", "POS", "pos"],
        "effect_allele": ["effect_allele", "EA", "A1", "alt"],
        "other_allele": ["other_allele", "OA", "A2", "ref"],
        "beta": ["beta", "BETA", "effect", "estimate", "log_odds", "lnOR"],
        "odds_ratio": ["odds_ratio", "OR", "or", "odds ratio", "oddsRatio"],
        "standard_error": ["standard_error", "SE", "se"],
        "effect_allele_frequency": ["effect_allele_frequency", "EAF", "eaf", "af"],
        "p_value": ["p_value", "P", "p", "pval"],
        "sample_size": ["n", "N", "sample_size", "samplesize"]
    }

    found_map = {}
    for group, candidates in expected_groups.items():
        found = [col for col in candidates if col in columns]
        found_map[group] = found[0] if len(found) > 0 else None

    if found_map["beta"] is not None:
        effect_size_type = "beta"
        effect_size_column = found_map["beta"]
    elif found_map["odds_ratio"] is not None:
        effect_size_type = "odds_ratio"
        effect_size_column = found_map["odds_ratio"]
    else:
        effect_size_type = "unknown"
        effect_size_column = None

    core_fields_without_effect = [
        "chromosome",
        "position",
        "effect_allele",
        "other_allele",
        "standard_error",
        "effect_allele_frequency",
        "p_value"
    ]

    missing_core = [field for field in core_fields_without_effect if found_map[field] is None]

    if effect_size_column is None:
        missing_core.append("effect_size")

    full_summary_stats_candidate = "Yes" if len(missing_core) == 0 else "No"

    if len(missing_core) == 0:
        if effect_size_type == "odds_ratio":
            status = "Needs adaptation"
            notes = "Effect size is represented as odds_ratio. Beta should be derived using beta = log(odds_ratio) before MR analysis."
        elif found_map["variant_identifier"] is None:
            status = "Needs adaptation"
            notes = "Core MR fields found, but no obvious rsID/SNP-like identifier column."
        else:
            status = "Suitable candidate"
            notes = "Core MR fields found; variant identifier present."
    else:
        status = "Not suitable for current pipeline"
        notes = f"Missing core fields: {', '.join(missing_core)}"

    found_map["effect_size_type"] = effect_size_type
    found_map["effect_size_column"] = effect_size_column

    return found_map, full_summary_stats_candidate, status, notes


def scan_single_file(file_record, preview_rows=5):
    file_path = Path(file_record["file_path"])
    df_small = read_preview_safely(file_path, nrows=preview_rows)
    columns = df_small.columns.tolist()

    found_map, full_summary_stats_candidate, status, notes = inspect_columns(columns)

    record = {
        "file_name": file_path.name,
        "file_path": str(file_path),
        "trait": file_record["trait"],
        "study_accession": strip_extension(file_path.name),
        "role": file_record["role"],
        "build": get_build_from_filename(file_path.name),
        "variant_identifier": found_map["variant_identifier"],
        "chromosome": found_map["chromosome"],
        "position": found_map["position"],
        "effect_allele": found_map["effect_allele"],
        "other_allele": found_map["other_allele"],
        "beta": found_map["beta"],
        "odds_ratio": found_map["odds_ratio"],
        "effect_size_column": found_map["effect_size_column"],
        "effect_size_type": found_map["effect_size_type"],
        "standard_error": found_map["standard_error"],
        "effect_allele_frequency": found_map["effect_allele_frequency"],
        "p_value": found_map["p_value"],
        "sample_size": found_map["sample_size"],
        "full_summary_stats_candidate": full_summary_stats_candidate,
        "status": status,
        "notes": notes
    }

    return df_small, record


def ensure_record_columns(df):
    required_columns = [
        "file_name",
        "file_path",
        "trait",
        "study_accession",
        "role",
        "build",
        "variant_identifier",
        "chromosome",
        "position",
        "effect_allele",
        "other_allele",
        "beta",
        "odds_ratio",
        "effect_size_column",
        "effect_size_type",
        "standard_error",
        "effect_allele_frequency",
        "p_value",
        "sample_size",
        "full_summary_stats_candidate",
        "status",
        "notes"
    ]

    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    return df


def load_target_record():
    if TARGET_RECORD_FILE.exists():
        df = pd.read_csv(TARGET_RECORD_FILE)
        df = ensure_record_columns(df)
        return df
    return pd.DataFrame()


def save_or_update_record(record_row: pd.DataFrame, record_file: Path):
    if record_file.exists():
        existing = pd.read_csv(record_file)
        existing = ensure_record_columns(existing)
        updated = pd.concat([existing, record_row], ignore_index=True)
    else:
        updated = record_row.copy()

    updated = updated.drop_duplicates(subset=["file_path"], keep="last")
    updated.to_csv(record_file, index=False)
    return updated


def merge_batch_with_existing(batch_df: pd.DataFrame, record_file: Path):
    """
    Batch scan updates automatic detection columns.
    If an old record exists, manual annotation fields are preserved when possible.
    """
    batch_df = ensure_record_columns(batch_df)

    if not record_file.exists():
        batch_df.to_csv(record_file, index=False)
        return batch_df

    old_df = pd.read_csv(record_file)
    old_df = ensure_record_columns(old_df)

    manual_columns = ["role", "trait", "study_accession", "build", "notes"]
    old_map = {
        str(row["file_path"]): row
        for _, row in old_df.iterrows()
    }

    updated_rows = []

    for _, new_row in batch_df.iterrows():
        row = new_row.copy()
        file_path = str(row["file_path"])

        if file_path in old_map:
            old_row = old_map[file_path]

            for col in manual_columns:
                old_value = old_row.get(col, "")
                new_value = row.get(col, "")

                if pd.notna(old_value) and str(old_value).strip() != "":
                    if col == "build":
                        # Use manually confirmed build if it is GRCh37/GRCh38.
                        # If old build is Unknown, keep filename-detected build.
                        if str(old_value) in ["GRCh37", "GRCh38"]:
                            row[col] = old_value
                    else:
                        row[col] = old_value

        updated_rows.append(row)

    updated = pd.DataFrame(updated_rows)

    # Keep old records that are no longer detected, in case files were temporarily moved.
    detected_paths = set(updated["file_path"].astype(str).tolist())
    old_only = old_df[~old_df["file_path"].astype(str).isin(detected_paths)]
    final_df = pd.concat([updated, old_only], ignore_index=True)

    final_df = final_df.drop_duplicates(subset=["file_path"], keep="last")
    final_df.to_csv(record_file, index=False)
    return final_df


# =========================================================
# Analysis set helpers
# =========================================================
REQUIRED_EXPOSURE_TRAITS = ["IGF1", "SHBG", "ADIPOQ", "GDF15"]

PREFERRED_EXPOSURE_FILES = [
    "GCST90237429_buildGRCh38.tsv.gz",  # ADIPOQ
    "GCST90179306_buildGRCh38.tsv.gz",  # GDF15
    "GCST90083018_buildGRCh38.tsv.gz",  # IGF1
    "GCST90079040_buildGRCh38.tsv.gz",  # SHBG
]


def canonical_trait_name(trait):
    key = re.sub(r"[^A-Z0-9]+", "", str(trait).upper())

    if "IGF1" in key or "INSULINLIKEGROWTHFACTOR1" in key:
        return "IGF1"
    if "SHBG" in key or "SEXHORMONEBINDINGGLOBULIN" in key:
        return "SHBG"
    if "ADIPOQ" in key or "ADIPONECTIN" in key:
        return "ADIPOQ"
    if "GDF15" in key or "GROWTHDIFFERENTIATIONFACTOR15" in key:
        return "GDF15"

    return key


def make_file_label(row):
    return (
        f'{row.get("file_name", "")} '
        f'({row.get("trait", "")}, {row.get("build", "")}, {row.get("status", "")})'
    )



# =========================================================
# Backend MR result helpers
# =========================================================
def read_csv_if_exists(path: Path):
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception as e:
            st.warning(f"Failed to read {path.name}: {e}")
            return pd.DataFrame()
    return pd.DataFrame()


def read_text_if_exists(path: Path):
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Failed to read {path.name}: {e}"
    return ""


def file_status_table(file_map: dict):
    records = []

    for label, path in file_map.items():
        path = Path(path)
        records.append({
            "output_name": label,
            "file_name": path.name,
            "exists": path.exists(),
            "size_MB": round(path.stat().st_size / 1024 / 1024, 3) if path.exists() else 0,
            "path": str(path)
        })

    return pd.DataFrame(records)


def show_download_button(df: pd.DataFrame, file_name: str, label: str):
    if df is not None and len(df) > 0:
        st.download_button(
            label=label,
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=file_name,
            mime="text/csv",
            key=make_unique_download_key("global_download_df", label, file_name)
        )

def format_backend_note():
    return """
    **Important interpretation note**

    The original coordinate-based backend MR results should be interpreted as prototype outputs. The updated LD clumping section provides a more formal MR improvement layer evidence.

    - Several selected GWAS files use coordinate-based variant identifiers instead of standard rsID.
    - Formal LD clumping has now been added in the updated MR pipeline through rsID mapping and TwoSampleMR LD clumping.
    - Outcome files using odds_ratio were adapted by converting odds_ratio to beta using beta = log(odds_ratio).
    - The current result is useful for checking backend feasibility, SNP overlap, harmonisation success, and outcome robustness.
    - The updated formal MR improvement should be interpreted together with the original coordinate-based prototype outputs. It now includes rsID mapping, LD clumping, and clumped MR rerun outputs. standard LD clumping.
    """


def summarise_multi_outcome_results(combined_df: pd.DataFrame, run_df: pd.DataFrame, overlap_df: pd.DataFrame):
    summary = {}

    if combined_df is not None and len(combined_df) > 0:
        summary["mr_result_rows"] = len(combined_df)

        if "nominal_significant" in combined_df.columns:
            summary["nominal_significant_rows"] = int(combined_df["nominal_significant"].fillna(False).sum())
        else:
            summary["nominal_significant_rows"] = 0

        if "trait" in combined_df.columns:
            summary["traits_with_results"] = combined_df["trait"].nunique()
        else:
            summary["traits_with_results"] = 0
    else:
        summary["mr_result_rows"] = 0
        summary["nominal_significant_rows"] = 0
        summary["traits_with_results"] = 0

    if run_df is not None and len(run_df) > 0:
        summary["successful_runs"] = int((run_df["status"].astype(str).str.lower() == "success").sum()) if "status" in run_df.columns else 0
        summary["failed_runs"] = int((run_df["status"].astype(str).str.lower() == "failed").sum()) if "status" in run_df.columns else 0
    else:
        summary["successful_runs"] = 0
        summary["failed_runs"] = 0

    if overlap_df is not None and len(overlap_df) > 0:
        summary["max_overlap_snps"] = int(pd.to_numeric(overlap_df.get("overlap_snps", pd.Series([0])), errors="coerce").max())
    else:
        summary["max_overlap_snps"] = 0

    return summary


def generate_quick_interpretation(combined_df: pd.DataFrame, run_df: pd.DataFrame, overlap_df: pd.DataFrame):
    lines = []

    if combined_df is None or len(combined_df) == 0:
        return "No combined MR result table is available yet."

    if "nominal_significant" in combined_df.columns:
        sig_count = int(combined_df["nominal_significant"].fillna(False).sum())
        if sig_count == 0:
            lines.append("No nominally significant MR association was detected in the current backend prototype.")
        else:
            lines.append(f"{sig_count} MR result row(s) reached nominal significance at p < 0.05.")

    # GDF15 direction
    if {"trait", "method", "MR_OR", "pval"}.issubset(set(combined_df.columns)):
        gdf15_ivw = combined_df[
            (combined_df["trait"].astype(str).str.upper() == "GDF15")
            & (combined_df["method"].astype(str).str.contains("Inverse variance weighted", case=False, na=False))
        ].copy()

        if len(gdf15_ivw) > 0:
            all_protective = (pd.to_numeric(gdf15_ivw["MR_OR"], errors="coerce") < 1).all()
            if all_protective:
                lines.append("GDF15 shows a consistent protective-direction estimate across usable outcome files, but this should not be treated as significant unless supported by p-values and confidence intervals.")
            else:
                lines.append("GDF15 direction is not fully consistent across usable outcome files.")

        shbg_ivw = combined_df[
            (combined_df["trait"].astype(str).str.upper() == "SHBG")
            & (combined_df["method"].astype(str).str.contains("Inverse variance weighted", case=False, na=False))
        ].copy()

        if len(shbg_ivw) > 0:
            shbg_or = pd.to_numeric(shbg_ivw["MR_OR"], errors="coerce")
            if (shbg_or < 1).any() and (shbg_or > 1).any():
                lines.append("SHBG does not show a stable direction across the tested outcome files.")
            else:
                lines.append("SHBG has a relatively consistent direction across the tested outcome files, but significance should be checked from p-values and confidence intervals.")

    if run_df is not None and len(run_df) > 0 and "status" in run_df.columns:
        success_count = int((run_df["status"].astype(str).str.lower() == "success").sum())
        failed_count = int((run_df["status"].astype(str).str.lower() == "failed").sum())
        lines.append(f"The multi-outcome backend run produced {success_count} successful exposure-outcome runs and {failed_count} failed runs.")

    if overlap_df is not None and len(overlap_df) > 0 and "overlap_snps" in overlap_df.columns:
        max_overlap = int(pd.to_numeric(overlap_df["overlap_snps"], errors="coerce").max())
        lines.append(f"The maximum observed exposure-outcome SNP overlap was {max_overlap} SNPs.")

    return " ".join(lines)


# =========================================================
# Sidebar navigation
# =========================================================
st.sidebar.title("🧬 MRDRP")
st.sidebar.write("**Targeted Artesunate Dashboard**")

page = st.sidebar.radio(
    "Go to",
    [
        "Home",
        "Targeted File Screening",
        "Analysis Set Selection",
        "Backend MR Results",
        "MR Pipeline + LD Clumping",
        "CPI / GNN Exploration"
    ],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.write("**Project root**")
st.sidebar.code(str(PROJECT_ROOT))
st.sidebar.write("**Exposure folder**")
st.sidebar.code(str(EXPOSURES_DIR))
st.sidebar.write("**Outcome folder**")
st.sidebar.code(str(OUTCOME_DIR))


# =========================================================
# Shared metrics
# =========================================================
all_target_files = list_all_target_files()
record_df = load_target_record()

file_count = len(all_target_files)
record_count = len(record_df)

analysis_set_count = 0
if ANALYSIS_SET_RECORD_FILE.exists():
    try:
        analysis_set_count = len(pd.read_csv(ANALYSIS_SET_RECORD_FILE))
    except Exception:
        analysis_set_count = 0


# =========================================================
# Page 1: Home
# =========================================================
if page == "Home":
    st.title("🧬 MRDRP Targeted Dashboard")
    st.caption("Targeted workflow for Artesunate-related exposure candidates and endometrial cancer outcome.")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Detected files", file_count)
    with c2:
        st.metric("Screening records", record_count)
    with c3:
        st.metric("Analysis sets", analysis_set_count)
    with c4:
        st.metric("Target route", "GRCh38")

    st.markdown("---")

    st.subheader("Supervisor-specified analysis direction")
    st.write(
        "The current targeted workflow focuses on extracting GWAS statistics for selected biological exposures "
        "related to the Artesunate repurposing hypothesis and applying MR analysis for endometrial cancer."
    )

    st.markdown(
        """
        **Target exposures**
        - IGF-1 / insulin-like growth factor 1
        - SHBG / sex hormone-binding globulin
        - Adiponectin / ADIPOQ
        - GDF-15 / growth differentiation factor 15

        **Target outcome**
        - Endometrial cancer
        """
    )

    st.info(
        "Current strategy: use the GRCh38 route as the main route. Some files may require adaptation, such as odds_ratio to beta conversion."
    )

    left, right = st.columns(2)

    with left:
        st.markdown(
            """
            <div class="nav-card">
                <h3>1. Targeted File Screening</h3>
                <p>Scan files from exposures/ and outcome/ folders, inspect GWAS columns, detect beta or odds_ratio, and save a targeted screening record.</p>
                <p class="small-note">Input files should be arranged by trait folders.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with right:
        st.markdown(
            """
            <div class="nav-card">
                <h3>2. Analysis Set Selection</h3>
                <p>Select multiple exposure files and one endometrial cancer outcome file to create an analysis set record.</p>
                <p class="small-note">This replaces the earlier one-to-one pair selection page.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.subheader("Detected folder structure")
    detected_df = pd.DataFrame(all_target_files)

    if len(detected_df) > 0:
        st.dataframe(detected_df, use_container_width=True)
    else:
        st.warning("No supported files detected in exposures/ or outcome/ folders yet.")

    if TARGET_RECORD_FILE.exists():
        st.subheader("Current targeted screening record")
        st.dataframe(load_target_record(), use_container_width=True)

    if ANALYSIS_SET_RECORD_FILE.exists():
        st.subheader("Current analysis set record")
        st.dataframe(pd.read_csv(ANALYSIS_SET_RECORD_FILE), use_container_width=True)


# =========================================================
# Page 2: Targeted File Screening
# =========================================================
elif page == "Targeted File Screening":
    st.title("📁 Targeted File Screening")
    st.caption("Screen files from exposures/ and outcome/ folders for the Artesunate/endometrial cancer direction.")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Detected files", file_count)
    with c2:
        st.metric("Screening records", record_count)
    with c3:
        st.metric("Record file", "Exists" if TARGET_RECORD_FILE.exists() else "Not created")

    st.markdown("---")

    with st.expander("Expected folder structure", expanded=True):
        st.code(
            """
MRDRP-main/
├── exposures/
│   ├── IGF1/
│   ├── SHBG/
│   ├── ADIPOQ/
│   └── GDF15/
│
└── outcome/
    └── endometrial_cancer/
            """,
            language="text"
        )

    if len(all_target_files) == 0:
        st.warning("No supported files found. Please add .tsv.gz, .tsv, .csv.gz, or .csv files into the exposure/outcome folders.")
        st.stop()

    file_options = [
        f'{item["role"]} | {item["trait"]} | {item["file_name"]}'
        for item in all_target_files
    ]

    selected_label = st.selectbox("Choose a file to inspect", file_options)
    selected_idx = file_options.index(selected_label)
    selected_record = all_target_files[selected_idx]

    preview_rows = st.slider("Preview rows", min_value=5, max_value=30, value=8)

    st.subheader("1) Selected file")
    st.code(selected_record["file_path"])

    try:
        df_preview, auto_record = scan_single_file(selected_record, preview_rows=preview_rows)
    except Exception as e:
        st.error("Failed to inspect the selected file.")
        st.exception(e)
        st.stop()

    st.subheader("2) Preview")
    st.dataframe(df_preview, use_container_width=True)

    st.subheader("3) Column names")
    st.code(str(df_preview.columns.tolist()), language="python")

    st.subheader("4) Automatic field check")

    check_columns = [
        "variant_identifier",
        "chromosome",
        "position",
        "effect_allele",
        "other_allele",
        "beta",
        "odds_ratio",
        "effect_size_column",
        "effect_size_type",
        "standard_error",
        "effect_allele_frequency",
        "p_value",
        "sample_size"
    ]

    check_df = pd.DataFrame({
        "Field group": check_columns,
        "Detected column": [auto_record.get(c, None) if auto_record.get(c, None) is not None else "Not found" for c in check_columns]
    })

    st.dataframe(check_df, use_container_width=True)

    left, right = st.columns(2)

    with left:
        st.info(f"Automatic status: **{auto_record['status']}**")
    with right:
        st.info(f"Effect size type: **{auto_record['effect_size_type']}**")

    st.write(f"**Automatic note:** {auto_record['notes']}")

    st.subheader("5) Manual annotation for targeted screening record")

    existing_record = None
    if TARGET_RECORD_FILE.exists():
        try:
            existing_df = load_target_record()
            matched = existing_df[existing_df["file_path"].astype(str) == str(selected_record["file_path"])]
            if len(matched) > 0:
                existing_record = matched.iloc[-1]
        except Exception:
            existing_record = None

    def get_existing_value(column_name, default_value=""):
        if existing_record is None:
            return default_value
        if column_name not in existing_record.index:
            return default_value
        value = existing_record[column_name]
        if pd.isna(value):
            return default_value
        return str(value)

    role_options = ["candidate", "exposure", "outcome"]
    build_options = ["Unknown", "GRCh37", "GRCh38"]

    default_role = get_existing_value("role", auto_record["role"]).lower()
    if default_role not in role_options:
        default_role = auto_record["role"]

    # Prefer manually confirmed GRCh37/GRCh38.
    # If old record is Unknown or empty, use filename-detected build.
    existing_build = get_existing_value("build", "")
    if existing_build in ["GRCh37", "GRCh38"]:
        default_build = existing_build
    else:
        default_build = auto_record["build"]

    if default_build not in build_options:
        default_build = "Unknown"

    default_trait = get_existing_value("trait", auto_record["trait"])
    default_study_accession = get_existing_value("study_accession", auto_record["study_accession"])
    default_notes = get_existing_value("notes", auto_record["notes"])

    unique_key = safe_widget_key(auto_record["file_path"])

    ann1, ann2, ann3 = st.columns(3)

    with ann1:
        role = st.selectbox(
            "Role",
            role_options,
            index=role_options.index(default_role),
            key=f"role_{unique_key}"
        )

    with ann2:
        trait = st.text_input(
            "Trait",
            value=default_trait,
            key=f"trait_{unique_key}"
        )

    with ann3:
        study_accession = st.text_input(
            "Study accession",
            value=default_study_accession,
            key=f"study_{unique_key}"
        )

    build = st.selectbox(
        "Genome build",
        build_options,
        index=build_options.index(default_build),
        key=f"build_{unique_key}"
    )

    manual_notes = st.text_area(
        "Extra notes",
        value=default_notes,
        height=100,
        key=f"notes_{unique_key}"
    )

    record_row = pd.DataFrame([{
        **auto_record,
        "role": role,
        "trait": trait,
        "study_accession": study_accession,
        "build": build,
        "notes": manual_notes
    }])

    st.subheader("6) Current targeted record preview")
    st.dataframe(record_row, use_container_width=True)

    if st.button("Save / Update this targeted record"):
        updated = save_or_update_record(record_row, TARGET_RECORD_FILE)
        st.success("Targeted screening record saved.")
        st.dataframe(updated, use_container_width=True)

    st.subheader("7) Batch scan all detected files")

    with st.expander("What does batch scan do?", expanded=False):
        st.write(
            "Batch scan automatically inspects all supported files under the exposures/ and outcome/ folders. "
            "It updates the targeted screening record using the current automatic detection rules. "
            "Existing manual annotations such as trait, role, confirmed build, and notes are preserved when possible."
        )

    if st.button("Scan all files and update targeted record"):
        records = []
        progress = st.progress(0)

        for idx, item in enumerate(all_target_files):
            try:
                _, rec = scan_single_file(item, preview_rows=5)
                records.append(rec)
            except Exception as e:
                st.warning(f"Failed to scan {item['file_name']}: {e}")

            progress.progress((idx + 1) / len(all_target_files))

        if len(records) > 0:
            batch_df = pd.DataFrame(records)
            combined = merge_batch_with_existing(batch_df, TARGET_RECORD_FILE)

            st.success("Batch scan completed and targeted record updated.")
            st.dataframe(combined, use_container_width=True)
        else:
            st.warning("No files were successfully scanned.")

    st.subheader("8) Existing targeted screening record")
    if TARGET_RECORD_FILE.exists():
        st.dataframe(load_target_record(), use_container_width=True)
    else:
        st.info("No targeted screening record exists yet.")


# =========================================================
# Page 3: Analysis Set Selection
# =========================================================
elif page == "Analysis Set Selection":
    st.title("🔗 Analysis Set Selection")
    st.caption("Select multiple exposure files and one endometrial cancer outcome file.")

    if not TARGET_RECORD_FILE.exists():
        st.warning("No targeted screening record found. Please scan and save targeted files first.")
        st.stop()

    screening_df = load_target_record()

    if "role" not in screening_df.columns:
        st.error("The targeted screening record does not contain a role column.")
        st.stop()

    screening_df["role_lower"] = screening_df["role"].astype(str).str.lower()

    exposure_df = screening_df[screening_df["role_lower"] == "exposure"].copy()
    outcome_df = screening_df[screening_df["role_lower"] == "outcome"].copy()

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Exposure records", len(exposure_df))
    with c2:
        st.metric("Outcome records", len(outcome_df))
    with c3:
        st.metric("Saved analysis sets", analysis_set_count)

    if len(exposure_df) == 0:
        st.warning("No exposure records found. Please label exposure files first.")
        st.stop()

    if len(outcome_df) == 0:
        st.warning("No outcome records found. Please label outcome files first.")
        st.stop()

    st.subheader("1) Select analysis set")

    default_set_name = "Artesunate_EndometrialCancer_GRCh38_Set01"

    analysis_set_name = st.text_input(
        "Analysis set name",
        value=default_set_name
    )

    # Build readable labels for exposure files.
    exposure_df["option_label"] = exposure_df.apply(make_file_label, axis=1)
    exposure_label_to_file = dict(zip(exposure_df["option_label"], exposure_df["file_name"]))
    exposure_file_to_label = dict(zip(exposure_df["file_name"], exposure_df["option_label"]))
    exposure_options = exposure_df["option_label"].tolist()

    # Default selection:
    # Prefer the four manually selected GRCh38 exposure files.
    preferred_defaults = [
        exposure_file_to_label[f]
        for f in PREFERRED_EXPOSURE_FILES
        if f in exposure_file_to_label
    ]

    # If preferred files are not all available, choose one available file per required trait.
    if len(preferred_defaults) < 4:
        fallback_defaults = []
        chosen_traits = set()

        for _, row in exposure_df.iterrows():
            canonical = canonical_trait_name(row.get("trait", ""))

            if canonical in REQUIRED_EXPOSURE_TRAITS and canonical not in chosen_traits:
                fallback_defaults.append(row["option_label"])
                chosen_traits.add(canonical)

        default_exposure_labels = fallback_defaults
    else:
        default_exposure_labels = preferred_defaults

    selected_exposure_labels = st.multiselect(
        "Select exposure files",
        options=exposure_options,
        default=default_exposure_labels
    )

    outcome_df["option_label"] = outcome_df.apply(make_file_label, axis=1)
    outcome_label_to_file = dict(zip(outcome_df["option_label"], outcome_df["file_name"]))
    outcome_options = outcome_df["option_label"].tolist()

    selected_outcome_label = st.selectbox(
        "Select outcome file",
        options=outcome_options
    )

    selected_exposure_files = [
        exposure_label_to_file[label]
        for label in selected_exposure_labels
    ]

    selected_outcome_file = outcome_label_to_file[selected_outcome_label]

    if len(selected_exposure_files) == 0:
        st.warning("Please select at least one exposure file.")
        st.stop()

    selected_exposures = exposure_df[exposure_df["file_name"].isin(selected_exposure_files)].copy()
    selected_outcome = outcome_df[outcome_df["file_name"] == selected_outcome_file].iloc[0]

    st.subheader("2) Selected files summary")

    exposure_summary = selected_exposures[[
        "file_name",
        "trait",
        "build",
        "status",
        "effect_size_type",
        "variant_identifier",
        "notes"
    ]].copy()

    outcome_summary = pd.DataFrame([{
        "file_name": selected_outcome.get("file_name", ""),
        "trait": selected_outcome.get("trait", ""),
        "build": selected_outcome.get("build", ""),
        "status": selected_outcome.get("status", ""),
        "effect_size_type": selected_outcome.get("effect_size_type", ""),
        "variant_identifier": selected_outcome.get("variant_identifier", ""),
        "notes": selected_outcome.get("notes", "")
    }])

    st.markdown("**Selected exposures**")
    st.dataframe(exposure_summary, use_container_width=True)

    st.markdown("**Selected outcome**")
    st.dataframe(outcome_summary, use_container_width=True)

    selected_canonical_traits = set(
        canonical_trait_name(t)
        for t in selected_exposures["trait"].astype(str).tolist()
    )

    missing_exposure_traits = [
        trait for trait in REQUIRED_EXPOSURE_TRAITS
        if trait not in selected_canonical_traits
    ]

    st.subheader("3) Analysis set readiness check")

    all_builds = selected_exposures["build"].astype(str).tolist() + [str(selected_outcome.get("build", "Unknown"))]
    unique_builds = sorted(list(set(all_builds)))

    if len(unique_builds) == 1 and unique_builds[0] != "Unknown":
        build_route = unique_builds[0]
        build_match = "Yes"
    elif len(unique_builds) == 1 and unique_builds[0] == "Unknown":
        build_route = "Unknown"
        build_match = "Uncertain"
    else:
        build_route = "; ".join(unique_builds)
        build_match = "No"

    statuses = selected_exposures["status"].astype(str).tolist() + [str(selected_outcome.get("status", ""))]

    has_not_suitable = any(s == "Not suitable for current pipeline" for s in statuses)
    has_adaptation = any(s == "Needs adaptation" for s in statuses)
    has_missing_required_exposures = len(missing_exposure_traits) > 0

    if has_missing_required_exposures:
        set_status = "Needs review"
        set_notes_default = (
            "The analysis set does not include all required exposure categories. "
            f"Missing exposure traits: {', '.join(missing_exposure_traits)}."
        )
    elif has_not_suitable:
        set_status = "Needs review"
        set_notes_default = "One or more selected files are not suitable for the current pipeline."
    elif build_match == "No":
        set_status = "Needs build harmonisation"
        set_notes_default = (
            "Selected files do not share the same genome build. Liftover or build harmonisation may be required."
        )
    elif build_match == "Uncertain":
        set_status = "Needs review"
        set_notes_default = "Genome build is unknown for one or more files. Build should be confirmed before MR analysis."
    elif build_match == "Yes" and has_adaptation:
        set_status = "Ready after adaptation"
        set_notes_default = (
            "All required exposure traits are selected and all files share the same genome build, "
            "but one or more files require adaptation before backend MR analysis. "
            "For example, odds_ratio may need conversion to beta, or variant identifiers may require mapping."
        )
    else:
        set_status = "Ready"
        set_notes_default = "All required exposure traits are selected, all files are suitable candidates, and all files share the same genome build."

    readiness_df = pd.DataFrame([{
        "analysis_set_name": analysis_set_name,
        "number_of_exposures": len(selected_exposures),
        "required_exposures": "; ".join(REQUIRED_EXPOSURE_TRAITS),
        "selected_exposure_traits": "; ".join(sorted(selected_canonical_traits)),
        "missing_exposure_traits": "; ".join(missing_exposure_traits) if missing_exposure_traits else "None",
        "outcome_file": selected_outcome_file,
        "build_route": build_route,
        "build_match": build_match,
        "has_adaptation": "Yes" if has_adaptation else "No",
        "has_not_suitable_file": "Yes" if has_not_suitable else "No",
        "set_status": set_status
    }])

    st.dataframe(readiness_df, use_container_width=True)

    if set_status == "Ready":
        st.success("This analysis set is technically ready.")
    elif set_status == "Ready after adaptation":
        st.info("This analysis set can be used after adaptation steps.")
    elif set_status == "Needs build harmonisation":
        st.warning("This analysis set needs build harmonisation before MR analysis.")
    else:
        st.error("This analysis set needs review before backend MR analysis.")

    st.subheader("4) Save analysis set record")

    set_notes = st.text_area(
        "Analysis set notes",
        value=set_notes_default,
        height=120
    )

    analysis_record = pd.DataFrame([{
        "analysis_set_name": analysis_set_name,
        "exposure_files": "; ".join(selected_exposures["file_name"].astype(str).tolist()),
        "exposure_traits": "; ".join(selected_exposures["trait"].astype(str).tolist()),
        "required_exposures": "; ".join(REQUIRED_EXPOSURE_TRAITS),
        "missing_exposure_traits": "; ".join(missing_exposure_traits) if missing_exposure_traits else "None",
        "outcome_file": selected_outcome_file,
        "outcome_trait": str(selected_outcome.get("trait", "")),
        "build_route": build_route,
        "build_match": build_match,
        "set_status": set_status,
        "notes": set_notes
    }])

    st.markdown("**Analysis set record preview**")
    st.dataframe(analysis_record, use_container_width=True)

    if st.button("Save / Update this analysis set"):
        if ANALYSIS_SET_RECORD_FILE.exists():
            existing_sets = pd.read_csv(ANALYSIS_SET_RECORD_FILE)
            updated_sets = pd.concat([existing_sets, analysis_record], ignore_index=True)
        else:
            updated_sets = analysis_record.copy()

        updated_sets = updated_sets.drop_duplicates(
            subset=["analysis_set_name"],
            keep="last"
        )

        updated_sets.to_csv(ANALYSIS_SET_RECORD_FILE, index=False)

        st.success("Analysis set record saved.")
        st.dataframe(updated_sets, use_container_width=True)

    st.subheader("5) Existing analysis set records")

    if ANALYSIS_SET_RECORD_FILE.exists():
        st.dataframe(pd.read_csv(ANALYSIS_SET_RECORD_FILE), use_container_width=True)
    else:
        st.info("No analysis set record exists yet.")


# =========================================================
# Page 4: Backend MR Results
# =========================================================
elif page == "Backend MR Results":
    st.title("📊 Backend MR Results")
    st.caption("Display backend MR outputs generated from the GRCh38 Artesunate/endometrial cancer workflow.")

    backend_file_map = {
        "Backend status report": BACKEND_STATUS_REPORT_FILE,
        "Multi-outcome comparison report": MULTI_OUTCOME_REPORT_FILE,
        "Significant variant QC": SIGNIFICANT_VARIANT_QC_FILE,
        "Single-outcome SNP overlap": SNP_OVERLAP_FILE,
        "Single-outcome MR run summary": COORDINATE_MR_RUN_SUMMARY_FILE,
        "Single-outcome combined MR results": COORDINATE_COMBINED_MR_RESULTS_FILE,
        "Multi-outcome preparation summary": MULTI_OUTCOME_PREPARE_SUMMARY_FILE,
        "Multi-outcome SNP overlap": MULTI_OUTCOME_SNP_OVERLAP_FILE,
        "Multi-outcome MR run summary": MULTI_OUTCOME_MR_RUN_SUMMARY_FILE,
        "Multi-outcome combined MR results": MULTI_OUTCOME_COMBINED_MR_RESULTS_FILE,
    }

    status_df = file_status_table(backend_file_map)

    existing_outputs = int(status_df["exists"].sum()) if len(status_df) > 0 else 0
    total_outputs = len(status_df)

    multi_prepare_df = read_csv_if_exists(MULTI_OUTCOME_PREPARE_SUMMARY_FILE)
    multi_overlap_df = read_csv_if_exists(MULTI_OUTCOME_SNP_OVERLAP_FILE)
    multi_run_df = read_csv_if_exists(MULTI_OUTCOME_MR_RUN_SUMMARY_FILE)
    multi_results_df = read_csv_if_exists(MULTI_OUTCOME_COMBINED_MR_RESULTS_FILE)
    sig_qc_df = read_csv_if_exists(SIGNIFICANT_VARIANT_QC_FILE)

    summary = summarise_multi_outcome_results(
        combined_df=multi_results_df,
        run_df=multi_run_df,
        overlap_df=multi_overlap_df
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Backend files found", f"{existing_outputs}/{total_outputs}")
    with c2:
        st.metric("Successful MR runs", summary["successful_runs"])
    with c3:
        st.metric("MR result rows", summary["mr_result_rows"])
    with c4:
        st.metric("Nominal significant rows", summary["nominal_significant_rows"])

    st.markdown("---")

    if existing_outputs == 0:
        st.warning(
            "No backend MR output files were detected yet. Please run the backend MR Colab cells first, then refresh this dashboard."
        )
        st.dataframe(status_df, use_container_width=True)
        st.stop()

    st.subheader("1) Backend output file status")
    st.dataframe(status_df, use_container_width=True)

    with st.expander("Backend output folder", expanded=False):
        st.code(str(MR_SUMMARY_DIR), language="text")

    st.subheader("2) Quick interpretation")
    quick_interpretation = generate_quick_interpretation(
        combined_df=multi_results_df,
        run_df=multi_run_df,
        overlap_df=multi_overlap_df
    )
    st.info(quick_interpretation)

    st.markdown(format_backend_note())

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview",
        "Outcome comparison",
        "MR results",
        "Reports",
        "Downloads"
    ])

    with tab1:
        st.subheader("Significant variant selection")

        if len(sig_qc_df) > 0:
            st.dataframe(sig_qc_df, use_container_width=True)
            show_download_button(sig_qc_df, "significant_variant_qc.csv", "Download significant variant QC")
        else:
            st.warning("Significant variant QC file is not available.")

        st.subheader("Multi-outcome MR run summary")

        if len(multi_run_df) > 0:
            st.dataframe(multi_run_df, use_container_width=True)

            if "status" in multi_run_df.columns:
                run_counts = (
                    multi_run_df["status"]
                    .astype(str)
                    .value_counts()
                    .reset_index()
                )
                run_counts.columns = ["status", "count"]
                st.markdown("**Run status counts**")
                st.dataframe(run_counts, use_container_width=True)

            show_download_button(multi_run_df, "multi_outcome_mr_run_summary.csv", "Download MR run summary")
        else:
            st.warning("Multi-outcome MR run summary is not available.")

    with tab2:
        st.subheader("Outcome preparation summary")

        if len(multi_prepare_df) > 0:
            st.dataframe(multi_prepare_df, use_container_width=True)

            if "status" in multi_prepare_df.columns:
                prepared_count = int((multi_prepare_df["status"].astype(str).str.lower() == "prepared").sum())
                failed_count = int((multi_prepare_df["status"].astype(str).str.lower() == "failed").sum())
                st.write(f"Prepared outcome files: **{prepared_count}**")
                st.write(f"Failed outcome files: **{failed_count}**")

            show_download_button(multi_prepare_df, "multi_outcome_prepare_summary.csv", "Download outcome preparation summary")
        else:
            st.warning("Multi-outcome preparation summary is not available.")

        st.subheader("SNP overlap summary")

        if len(multi_overlap_df) > 0:
            st.dataframe(multi_overlap_df, use_container_width=True)

            if {"set_name", "trait", "overlap_snps"}.issubset(set(multi_overlap_df.columns)):
                overlap_view = multi_overlap_df[["set_name", "trait", "exposure_snps", "outcome_snps", "overlap_snps"]].copy()
                st.markdown("**Overlap comparison view**")
                st.dataframe(overlap_view, use_container_width=True)

            show_download_button(multi_overlap_df, "multi_outcome_snp_overlap.csv", "Download SNP overlap summary")
        else:
            st.warning("Multi-outcome SNP overlap summary is not available.")

    with tab3:
        st.subheader("Combined MR results")

        if len(multi_results_df) > 0:
            filter_cols = st.columns(3)

            filtered_df = multi_results_df.copy()

            with filter_cols[0]:
                if "trait" in filtered_df.columns:
                    trait_options = ["All"] + sorted(filtered_df["trait"].dropna().astype(str).unique().tolist())
                    selected_trait = st.selectbox("Filter by trait", trait_options)
                    if selected_trait != "All":
                        filtered_df = filtered_df[filtered_df["trait"].astype(str) == selected_trait]

            with filter_cols[1]:
                if "method" in filtered_df.columns:
                    method_options = ["All"] + sorted(filtered_df["method"].dropna().astype(str).unique().tolist())
                    selected_method = st.selectbox("Filter by MR method", method_options)
                    if selected_method != "All":
                        filtered_df = filtered_df[filtered_df["method"].astype(str) == selected_method]

            with filter_cols[2]:
                show_primary_cols_only = st.checkbox("Show simplified columns", value=True)

            if "pval" in filtered_df.columns:
                filtered_df["pval"] = pd.to_numeric(filtered_df["pval"], errors="coerce")
                filtered_df = filtered_df.sort_values("pval", ascending=True)

            if show_primary_cols_only:
                primary_cols = [
                    "set_name",
                    "trait",
                    "method",
                    "nsnp",
                    "b",
                    "se",
                    "pval",
                    "MR_OR",
                    "MR_OR_lower_95CI",
                    "MR_OR_upper_95CI",
                    "nominal_significant",
                    "overlap_snps"
                ]
                display_cols = [c for c in primary_cols if c in filtered_df.columns]
                st.dataframe(filtered_df[display_cols], use_container_width=True)
            else:
                st.dataframe(filtered_df, use_container_width=True)

            show_download_button(filtered_df, "filtered_multi_outcome_mr_results.csv", "Download filtered MR results")

            st.markdown("**Interpretation guide**")
            st.write(
                "MR_OR < 1 suggests a protective-direction estimate, while MR_OR > 1 suggests a risk-increasing direction. "
                "However, the current results are prototype outputs and should not be interpreted as final formal causal evidence."
            )
        else:
            st.warning("Multi-outcome combined MR results are not available.")

    with tab4:
        st.subheader("Backend status report")

        backend_report_text = read_text_if_exists(BACKEND_STATUS_REPORT_FILE)
        if backend_report_text:
            st.markdown(backend_report_text)
        else:
            st.info("Single-outcome backend status report is not available.")

        st.subheader("Multi-outcome comparison report")

        multi_report_text = read_text_if_exists(MULTI_OUTCOME_REPORT_FILE)
        if multi_report_text:
            with st.expander("Show full multi-outcome comparison report", expanded=False):
                report_view_mode = st.radio(
                    "Report display mode",
                    ["Readable text", "Rendered markdown"],
                    horizontal=True,
                    key="multi_outcome_report_view_mode"
                )

                if report_view_mode == "Readable text":
                    st.text_area(
                        "Full report markdown text",
                        value=multi_report_text,
                        height=650
                    )
                else:
                    st.markdown(multi_report_text)

                st.download_button(
                    label="Download multi-outcome comparison report",
                    data=multi_report_text.encode("utf-8"),
                    file_name="multi_outcome_backend_mr_comparison_report.md",
                    mime="text/markdown"
                )
        else:
            st.info("Multi-outcome comparison report is not available.")

    with tab5:
        st.subheader("Available backend result files")

        st.dataframe(status_df, use_container_width=True)

        st.write("Use the buttons below to download key result tables.")

        if len(multi_results_df) > 0:
            show_download_button(multi_results_df, "multi_outcome_combined_mr_results.csv", "Download combined MR results")

        if len(multi_overlap_df) > 0:
            show_download_button(multi_overlap_df, "multi_outcome_snp_overlap.csv", "Download multi-outcome SNP overlap")

        if len(multi_run_df) > 0:
            show_download_button(multi_run_df, "multi_outcome_mr_run_summary.csv", "Download multi-outcome MR run summary")

        if len(multi_prepare_df) > 0:
            show_download_button(multi_prepare_df, "multi_outcome_prepare_summary.csv", "Download multi-outcome preparation summary")



# =========================================================
# Page 5: MR Pipeline + LD Clumping
# =========================================================
if page == "MR Pipeline + LD Clumping":
    st.title("🧬 MR Pipeline + LD Clumping")
    st.caption("Integrated MR pipeline view with rsID mapping, LD clumping, and clumped MR rerun outputs.")

    def _read_csv(path: Path):
        if path.exists():
            try:
                return pd.read_csv(path)
            except Exception as e:
                st.warning(f"Failed to read {path.name}: {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    def _read_text(path: Path):
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception as e:
                return f"Failed to read {path.name}: {e}"
        return ""



    def _download_df(df: pd.DataFrame, file_name: str, label: str):
        if df is not None and len(df) > 0:
            st.download_button(
                label=label,
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=file_name,
                mime="text/csv",
                key=make_unique_download_key("ld_download_df", label, file_name)
            )


    def _download_text(text: str, file_name: str, label: str):
        if text is not None and len(text.strip()) > 0:
            st.download_button(
                label=label,
                data=text.encode("utf-8"),
                file_name=file_name,
                mime="text/markdown",
                key=make_unique_download_key("ld_download_text", label, file_name)
            )

    ld_file_map = {
        "rsID mapping summary": RSID_MAPPING_SUMMARY_FILE,
        "LD clumping input summary": LD_CLUMPING_INPUT_SUMMARY_FILE,
        "LD clumping summary": LD_CLUMPING_SUMMARY_FILE,
        "MR-ready clumped exposure summary": MR_READY_CLUMPED_EXPOSURE_SUMMARY_FILE,
        "Clumped multi-outcome SNP overlap": CLUMPED_MULTI_OUTCOME_SNP_OVERLAP_FILE,
        "Clumped multi-outcome MR run summary": CLUMPED_MULTI_OUTCOME_MR_RUN_SUMMARY_FILE,
        "Clumped multi-outcome combined MR results": CLUMPED_MULTI_OUTCOME_COMBINED_MR_RESULTS_FILE,
        "LD clumping improvement report": LD_CLUMPING_IMPROVEMENT_REPORT_FILE,
    }

    ld_status_records = []
    for output_name, path in ld_file_map.items():
        path = Path(path)
        ld_status_records.append({
            "output_name": output_name,
            "file_name": path.name,
            "exists": path.exists(),
            "size_MB": round(path.stat().st_size / 1024 / 1024, 3) if path.exists() else 0,
            "path": str(path)
        })
    ld_status_df = pd.DataFrame(ld_status_records)

    rsid_df = _read_csv(RSID_MAPPING_SUMMARY_FILE)
    ld_input_df = _read_csv(LD_CLUMPING_INPUT_SUMMARY_FILE)
    ld_summary_df = _read_csv(LD_CLUMPING_SUMMARY_FILE)
    mr_ready_clumped_df = _read_csv(MR_READY_CLUMPED_EXPOSURE_SUMMARY_FILE)
    clumped_overlap_df = _read_csv(CLUMPED_MULTI_OUTCOME_SNP_OVERLAP_FILE)
    clumped_run_df = _read_csv(CLUMPED_MULTI_OUTCOME_MR_RUN_SUMMARY_FILE)
    clumped_results_df = _read_csv(CLUMPED_MULTI_OUTCOME_COMBINED_MR_RESULTS_FILE)
    ld_report_text = _read_text(LD_CLUMPING_IMPROVEMENT_REPORT_FILE)

    # --------------------------------------------------------
    # Top metrics
    # --------------------------------------------------------

    existing_ld_outputs = int(ld_status_df["exists"].sum()) if len(ld_status_df) > 0 else 0
    total_ld_outputs = len(ld_status_df)

    mapped_variants = 0
    total_variants = 0
    if len(rsid_df) > 0:
        if "mapped_rsid_count" in rsid_df.columns:
            mapped_variants = int(pd.to_numeric(rsid_df["mapped_rsid_count"], errors="coerce").fillna(0).sum())
        if "total_variants" in rsid_df.columns:
            total_variants = int(pd.to_numeric(rsid_df["total_variants"], errors="coerce").fillna(0).sum())

    clumped_variants = 0
    input_variants = 0
    if len(ld_summary_df) > 0:
        if "input_variants" in ld_summary_df.columns:
            input_variants = int(pd.to_numeric(ld_summary_df["input_variants"], errors="coerce").fillna(0).sum())
        if "clumped_variants" in ld_summary_df.columns:
            clumped_variants = int(pd.to_numeric(ld_summary_df["clumped_variants"], errors="coerce").fillna(0).sum())

    successful_clumped_runs = 0
    if len(clumped_run_df) > 0 and "status" in clumped_run_df.columns:
        successful_clumped_runs = int((clumped_run_df["status"].astype(str).str.lower() == "success").sum())

    nominal_sig_rows = 0
    if len(clumped_results_df) > 0 and "nominal_significant" in clumped_results_df.columns:
        nominal_sig_rows = int(clumped_results_df["nominal_significant"].fillna(False).sum())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("LD output files found", f"{existing_ld_outputs}/{total_ld_outputs}")
    with c2:
        st.metric("Mapped rsID variants", f"{mapped_variants}/{total_variants}")
    with c3:
        st.metric("LD-clumped variants", f"{clumped_variants}/{input_variants}")
    with c4:
        st.metric("Clumped MR significant rows", nominal_sig_rows)

    st.markdown("---")

    # --------------------------------------------------------
    # Quick interpretation
    # --------------------------------------------------------

    st.subheader("1) Quick interpretation")

    interpretation_lines = []

    if mapped_variants > 0 and total_variants > 0:
        mapping_rate = mapped_variants / total_variants
        interpretation_lines.append(
            f"Coordinate-based variants were mapped to rsID with an overall mapping rate of {mapping_rate:.2%} "
            f"({mapped_variants}/{total_variants})."
        )

    if input_variants > 0:
        interpretation_lines.append(
            f"LD clumping reduced the candidate instruments from {input_variants} mapped variants to {clumped_variants} independent variants."
        )

    if len(ld_summary_df) > 0 and {"trait", "input_variants", "clumped_variants"}.issubset(set(ld_summary_df.columns)):
        trait_parts = []
        for _, row in ld_summary_df.iterrows():
            trait_parts.append(
                f"{row['trait']}: {int(row['input_variants'])} to {int(row['clumped_variants'])}"
            )
        interpretation_lines.append("Trait-level clumping result: " + "; ".join(trait_parts) + ".")

    if len(clumped_run_df) > 0:
        failed_clumped_runs = int((clumped_run_df["status"].astype(str).str.lower() == "failed").sum()) if "status" in clumped_run_df.columns else 0
        interpretation_lines.append(
            f"The clumped MR rerun produced {successful_clumped_runs} successful exposure-outcome runs and {failed_clumped_runs} failed runs."
        )

    if len(clumped_results_df) > 0:
        traits = sorted(clumped_results_df["trait"].dropna().astype(str).unique().tolist()) if "trait" in clumped_results_df.columns else []
        interpretation_lines.append(
            f"The clumped combined MR table contains {len(clumped_results_df)} result rows for trait(s): {', '.join(traits)}."
        )
        if nominal_sig_rows == 0:
            interpretation_lines.append(
                "No nominally significant association was detected in the LD-clumped MR results."
            )
        else:
            interpretation_lines.append(
                f"{nominal_sig_rows} result row(s) reached nominal significance at p < 0.05."
            )

    if len(interpretation_lines) == 0:
        st.warning("LD clumping outputs are not available yet. Please run the LD clumping backend cells first.")
    else:
        st.info(" ".join(interpretation_lines))

    st.markdown(
        """
        Important note:
        The previous coordinate-based MR results are retained as backend prototype outputs.
        The updated LD clumping workflow is more formal because it maps coordinate-based variants to rsID,
        performs LD clumping, and reruns MR using LD-clumped instruments.
        However, after clumping, usable instruments are limited. GDF15 did not retain usable harmonised instruments,
        while SHBG produced limited single-SNP Wald ratio results in the first three outcome candidates.
        """
    )

    # --------------------------------------------------------
    # Tabs
    # --------------------------------------------------------

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Pipeline status",
        "rsID mapping",
        "LD clumping",
        "Clumped MR results",
        "Report",
        "Downloads"
    ])

    with tab1:
        st.subheader("LD clumping output file status")
        st.dataframe(ld_status_df, use_container_width=True)

        st.subheader("Integrated MR pipeline steps")
        pipeline_steps = pd.DataFrame([
            {"step": "1", "pipeline_step": "Selected GRCh38 analysis set", "output": "analysis_set_record.csv", "status": "Completed"},
            {"step": "2", "pipeline_step": "GWAS preprocessing and standardisation", "output": "backend_preprocessing_summary.csv", "status": "Completed"},
            {"step": "3", "pipeline_step": "Significant variant selection", "output": "significant_variant_qc.csv", "status": "Completed"},
            {"step": "4", "pipeline_step": "Coordinate-based variant to rsID mapping", "output": "rsid_mapping_summary.csv", "status": "Completed" if len(rsid_df) > 0 else "Not available"},
            {"step": "5", "pipeline_step": "LD clumping", "output": "ld_clumping_summary.csv", "status": "Completed" if len(ld_summary_df) > 0 else "Not available"},
            {"step": "6", "pipeline_step": "Clumped exposure-outcome SNP overlap", "output": "clumped_multi_outcome_snp_overlap.csv", "status": "Completed" if len(clumped_overlap_df) > 0 else "Not available"},
            {"step": "7", "pipeline_step": "Clumped MR rerun", "output": "clumped_multi_outcome_combined_mr_results.csv", "status": "Completed" if len(clumped_results_df) > 0 else "Not available"},
            {"step": "8", "pipeline_step": "Dashboard display and report generation", "output": "ld_clumping_improvement_report.md", "status": "Completed" if len(ld_report_text) > 0 else "Not available"},
        ])
        st.dataframe(pipeline_steps, use_container_width=True)

    with tab2:
        st.subheader("rsID mapping summary")
        if len(rsid_df) > 0:
            st.dataframe(rsid_df, use_container_width=True)
            _download_df(rsid_df, "rsid_mapping_summary.csv", "Download rsID mapping summary")
        else:
            st.warning("rsID mapping summary is not available.")

    with tab3:
        st.subheader("LD clumping input summary")
        if len(ld_input_df) > 0:
            st.dataframe(ld_input_df, use_container_width=True)
            _download_df(ld_input_df, "ld_clumping_input_summary.csv", "Download LD clumping input summary")
        else:
            st.warning("LD clumping input summary is not available.")

        st.subheader("LD clumping summary")
        if len(ld_summary_df) > 0:
            st.dataframe(ld_summary_df, use_container_width=True)
            _download_df(ld_summary_df, "ld_clumping_summary.csv", "Download LD clumping summary")
        else:
            st.warning("LD clumping summary is not available.")

        st.subheader("MR-ready clumped exposure summary")
        if len(mr_ready_clumped_df) > 0:
            st.dataframe(mr_ready_clumped_df, use_container_width=True)
            _download_df(mr_ready_clumped_df, "mr_ready_clumped_exposure_summary.csv", "Download MR-ready clumped exposure summary")
        else:
            st.warning("MR-ready clumped exposure summary is not available.")

    with tab4:
        st.subheader("Clumped exposure-outcome SNP overlap")
        if len(clumped_overlap_df) > 0:
            st.dataframe(clumped_overlap_df, use_container_width=True)
            _download_df(clumped_overlap_df, "clumped_multi_outcome_snp_overlap.csv", "Download clumped SNP overlap")
        else:
            st.warning("Clumped SNP overlap file is not available.")

        st.subheader("Clumped MR run summary")
        if len(clumped_run_df) > 0:
            st.dataframe(clumped_run_df, use_container_width=True)
            _download_df(clumped_run_df, "clumped_multi_outcome_mr_run_summary.csv", "Download clumped MR run summary")
        else:
            st.warning("Clumped MR run summary is not available.")

        st.subheader("Clumped combined MR results")
        if len(clumped_results_df) > 0:
            filtered_df = clumped_results_df.copy()

            filter_cols = st.columns(3)

            with filter_cols[0]:
                if "trait" in filtered_df.columns:
                    trait_options = ["All"] + sorted(filtered_df["trait"].dropna().astype(str).unique().tolist())
                    selected_trait = st.selectbox("Filter by trait", trait_options, key="clumped_result_trait_filter")
                    if selected_trait != "All":
                        filtered_df = filtered_df[filtered_df["trait"].astype(str) == selected_trait]

            with filter_cols[1]:
                if "method" in filtered_df.columns:
                    method_options = ["All"] + sorted(filtered_df["method"].dropna().astype(str).unique().tolist())
                    selected_method = st.selectbox("Filter by method", method_options, key="clumped_result_method_filter")
                    if selected_method != "All":
                        filtered_df = filtered_df[filtered_df["method"].astype(str) == selected_method]

            with filter_cols[2]:
                simplified = st.checkbox("Show simplified columns", value=True, key="clumped_result_simplified_cols")

            if "pval" in filtered_df.columns:
                filtered_df["pval"] = pd.to_numeric(filtered_df["pval"], errors="coerce")
                filtered_df = filtered_df.sort_values("pval", ascending=True)

            if simplified:
                primary_cols = [
                    "set_name",
                    "trait",
                    "method",
                    "nsnp",
                    "b",
                    "se",
                    "pval",
                    "MR_OR",
                    "MR_OR_lower_95CI",
                    "MR_OR_upper_95CI",
                    "nominal_significant",
                    "harmonised_snps",
                    "instrument_selection",
                    "overlap_snps"
                ]
                display_cols = [c for c in primary_cols if c in filtered_df.columns]
                st.dataframe(filtered_df[display_cols], use_container_width=True)
            else:
                st.dataframe(filtered_df, use_container_width=True)

            _download_df(filtered_df, "filtered_clumped_multi_outcome_mr_results.csv", "Download filtered clumped MR results")

            st.markdown("Interpretation guide:")
            st.write(
                "The LD-clumped MR results are more conservative than the previous coordinate-based prototype results. "
                "SHBG currently has single-SNP Wald ratio results only, while GDF15 did not retain usable harmonised instruments after clumping. "
                "Wide confidence intervals should be interpreted as limited statistical stability."
            )
        else:
            st.warning("Clumped combined MR results are not available.")

    with tab5:
        st.subheader("LD clumping improvement report")
        if ld_report_text:
            view_mode = st.radio(
                "Report display mode",
                ["Readable text", "Rendered markdown"],
                horizontal=True,
                key="ld_report_view_mode"
            )
            if view_mode == "Readable text":
                st.text_area("Full LD clumping report markdown text", value=ld_report_text, height=650)
            else:
                st.markdown(ld_report_text)
            _download_text(ld_report_text, "ld_clumping_improvement_report.md", "Download LD clumping improvement report")
        else:
            st.info("LD clumping improvement report is not available.")

    with tab6:
        st.subheader("Available LD clumping result files")
        st.dataframe(ld_status_df, use_container_width=True)

        if len(rsid_df) > 0:
            _download_df(rsid_df, "rsid_mapping_summary.csv", "Download rsID mapping summary")
        if len(ld_summary_df) > 0:
            _download_df(ld_summary_df, "ld_clumping_summary.csv", "Download LD clumping summary")
        if len(clumped_overlap_df) > 0:
            _download_df(clumped_overlap_df, "clumped_multi_outcome_snp_overlap.csv", "Download clumped SNP overlap")
        if len(clumped_run_df) > 0:
            _download_df(clumped_run_df, "clumped_multi_outcome_mr_run_summary.csv", "Download clumped MR run summary")
        if len(clumped_results_df) > 0:
            _download_df(clumped_results_df, "clumped_multi_outcome_combined_mr_results.csv", "Download clumped combined MR results")
        if ld_report_text:
            _download_text(ld_report_text, "ld_clumping_improvement_report.md", "Download LD clumping report")



# =========================================================
# Page 6: CPI / GNN Exploration
# =========================================================
if page == "CPI / GNN Exploration":
    st.title("🧪 CPI / GNN Exploration")
    st.caption("Compound-protein interaction prediction exploration using the CPI_prediction repository.")

    def _cpi_read_csv(path: Path):
        path = Path(path)
        if path.exists():
            try:
                return pd.read_csv(path)
            except Exception as e:
                st.warning(f"Failed to read {path.name}: {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    def _cpi_read_text(path: Path):
        path = Path(path)
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception as e:
                return f"Failed to read {path.name}: {e}"
        return ""


    def _cpi_download_df(df: pd.DataFrame, file_name: str, label: str):
        if df is not None and len(df) > 0:
            st.download_button(
                label=label,
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=file_name,
                mime="text/csv",
                key=make_unique_cpi_download_key("cpi_df", label, file_name)
            )


    def _cpi_download_text(text: str, file_name: str, label: str):
        if text is not None and len(text.strip()) > 0:
            st.download_button(
                label=label,
                data=text.encode("utf-8"),
                file_name=file_name,
                mime="text/markdown",
                key=make_unique_cpi_download_key("cpi_text", label, file_name)
            )

    cpi_file_map = {
        "CPI exploration status": CPI_EXPLORATION_STATUS_FILE,
        "CPI exploration summary": CPI_EXPLORATION_SUMMARY_FILE,
        "Quick training log": CPI_QUICK_TRAINING_LOG_FILE,
        "Quick evaluation log": CPI_QUICK_EVALUATION_LOG_FILE,
        "Quick evaluation metrics": CPI_QUICK_EVALUATION_METRICS_FILE,
        "Quick confusion matrix": CPI_QUICK_CONFUSION_MATRIX_FILE,
        "Quick classification report": CPI_QUICK_CLASSIFICATION_REPORT_FILE,
        "Quick test predictions": CPI_QUICK_TEST_PREDICTIONS_FILE,
        "Artesunate SMILES": CPI_ARTESUNATE_SMILES_FILE,
        "Candidate protein target template": CPI_CANDIDATE_TARGET_TEMPLATE_FILE,
    }

    cpi_status_records = []

    for output_name, path in cpi_file_map.items():
        path = Path(path)
        cpi_status_records.append({
            "output_name": output_name,
            "file_name": path.name,
            "exists": path.exists(),
            "size_KB": round(path.stat().st_size / 1024, 2) if path.exists() else 0,
            "path": str(path),
        })

    cpi_status_df = pd.DataFrame(cpi_status_records)

    cpi_metrics_df = _cpi_read_csv(CPI_QUICK_EVALUATION_METRICS_FILE)
    cpi_cm_df = _cpi_read_csv(CPI_QUICK_CONFUSION_MATRIX_FILE)
    cpi_report_df = _cpi_read_csv(CPI_QUICK_CLASSIFICATION_REPORT_FILE)
    cpi_predictions_df = _cpi_read_csv(CPI_QUICK_TEST_PREDICTIONS_FILE)
    cpi_artesunate_df = _cpi_read_csv(CPI_ARTESUNATE_SMILES_FILE)
    cpi_targets_df = _cpi_read_csv(CPI_CANDIDATE_TARGET_TEMPLATE_FILE)
    cpi_summary_text = _cpi_read_text(CPI_EXPLORATION_SUMMARY_FILE)
    cpi_train_log = _cpi_read_text(CPI_QUICK_TRAINING_LOG_FILE)
    cpi_eval_log = _cpi_read_text(CPI_QUICK_EVALUATION_LOG_FILE)

    existing_outputs = int(cpi_status_df["exists"].sum()) if len(cpi_status_df) > 0 else 0
    total_outputs = len(cpi_status_df)

    accuracy_value = "N/A"
    auc_value = "N/A"
    f1_value = "N/A"
    n_test_value = "N/A"

    if len(cpi_metrics_df) > 0:
        if "accuracy" in cpi_metrics_df.columns:
            accuracy_value = round(float(cpi_metrics_df["accuracy"].iloc[0]), 3)
        if "auc" in cpi_metrics_df.columns:
            auc_value = round(float(cpi_metrics_df["auc"].iloc[0]), 3)
        if "f1" in cpi_metrics_df.columns:
            f1_value = round(float(cpi_metrics_df["f1"].iloc[0]), 3)
        if "n_test" in cpi_metrics_df.columns:
            n_test_value = int(cpi_metrics_df["n_test"].iloc[0])

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("CPI output files found", f"{existing_outputs}/{total_outputs}")
    with c2:
        st.metric("Quick test AUC", auc_value)
    with c3:
        st.metric("Quick test F1-score", f1_value)
    with c4:
        st.metric("Quick test size", n_test_value)

    st.markdown("---")

    st.subheader("1) Quick interpretation")

    interpretation_text = (
        "This page integrates the CPI / GNN exploration backend into the MRDRP dashboard. "
        "The CPI module is used to explore compound-protein interaction prediction. "
        "In the current exploration, the CPI_prediction repository was adapted to the Colab environment, "
        "preprocessed successfully, trained on a quick subset using GPU, and evaluated with classification metrics. "
        "This is a feasibility module rather than a final molecular interaction prediction benchmark."
    )

    if len(cpi_metrics_df) > 0:
        interpretation_text += (
            f" In the quick evaluation, the model reached AUC={auc_value}, "
            f"F1-score={f1_value}, and accuracy={accuracy_value} on a small test split."
        )

    st.info(interpretation_text)

    st.markdown(
        """
        Important note:
        The current CPI model is based on compound SMILES converted to molecular graph features and protein amino acid sequences.
        It is a GNN-CNN style CPI prediction model, but not yet a full 3D coordinate-based GNN.
        This module should be interpreted as a feasibility exploration before future Artesunate-protein prediction or true 3D GNN extension.
        """
    )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Pipeline status",
        "Quick metrics",
        "Confusion matrix",
        "Compound and targets",
        "Summary report",
        "Downloads"
    ])

    with tab1:
        st.subheader("CPI exploration output status")
        st.dataframe(cpi_status_df, use_container_width=True)

        st.subheader("CPI / GNN pipeline steps")
        cpi_pipeline_steps = pd.DataFrame([
            {"step": "1", "pipeline_step": "Clone CPI_prediction repository", "output": "CPI_prediction folder", "status": "Completed" if CPI_REPO_ROOT.exists() else "Not available"},
            {"step": "2", "pipeline_step": "Install RDKit and dependencies", "output": "Colab environment", "status": "Completed"},
            {"step": "3", "pipeline_step": "Patch legacy NumPy loading/saving", "output": "preprocess_data.py and run_training.py", "status": "Completed"},
            {"step": "4", "pipeline_step": "Preprocess CPI dataset", "output": "compound/protein tensors", "status": "Completed" if CPI_QUICK_TRAINING_LOG_FILE.exists() else "Not available"},
            {"step": "5", "pipeline_step": "Quick GPU training", "output": "quick model and AUC output", "status": "Completed" if CPI_QUICK_TRAINING_LOG_FILE.exists() else "Not available"},
            {"step": "6", "pipeline_step": "Quick classification evaluation", "output": "metrics/confusion matrix/report", "status": "Completed" if CPI_QUICK_EVALUATION_METRICS_FILE.exists() else "Not available"},
            {"step": "7", "pipeline_step": "Prepare Artesunate SMILES", "output": "artesunate_smiles_pubchem.csv", "status": "Completed" if CPI_ARTESUNATE_SMILES_FILE.exists() else "Not available"},
            {"step": "8", "pipeline_step": "Prepare candidate target template", "output": "candidate_protein_target_template.csv", "status": "Completed" if CPI_CANDIDATE_TARGET_TEMPLATE_FILE.exists() else "Not available"},
        ])
        st.dataframe(cpi_pipeline_steps, use_container_width=True)

    with tab2:
        st.subheader("Quick evaluation metrics")
        if len(cpi_metrics_df) > 0:
            st.dataframe(cpi_metrics_df, use_container_width=True)
            _cpi_download_df(cpi_metrics_df, "quick_evaluation_metrics.csv", "Download quick evaluation metrics")
        else:
            st.warning("Quick evaluation metrics are not available.")

        st.subheader("Classification report")
        if len(cpi_report_df) > 0:
            st.dataframe(cpi_report_df, use_container_width=True)
            _cpi_download_df(cpi_report_df, "quick_classification_report.csv", "Download classification report")
        else:
            st.warning("Classification report is not available.")

        st.subheader("Prediction preview")
        if len(cpi_predictions_df) > 0:
            st.dataframe(cpi_predictions_df.head(100), use_container_width=True)
            _cpi_download_df(cpi_predictions_df, "quick_test_predictions.csv", "Download quick test predictions")
        else:
            st.warning("Quick test prediction table is not available.")

    with tab3:
        st.subheader("Confusion matrix")
        if len(cpi_cm_df) > 0:
            st.dataframe(cpi_cm_df, use_container_width=True)

            try:
                cm_display = cpi_cm_df.copy()
                first_col = cm_display.columns[0]
                if first_col.lower().startswith("unnamed") or first_col == "":
                    cm_display = cm_display.set_index(first_col)

                numeric_cm = cm_display.select_dtypes(include=["number"])

                if numeric_cm.shape[0] > 0 and numeric_cm.shape[1] > 0:
                    st.markdown("Confusion matrix heatmap")
                    st.dataframe(numeric_cm.style.background_gradient(axis=None), use_container_width=True)
            except Exception as e:
                st.info(f"Heatmap rendering skipped: {e}")

            _cpi_download_df(cpi_cm_df, "quick_confusion_matrix.csv", "Download confusion matrix")
        else:
            st.warning("Confusion matrix is not available.")

        st.markdown(
            """
            Confusion matrix guide:
            - True positive: actual interaction and predicted interaction.
            - True negative: actual non-interaction and predicted non-interaction.
            - False positive: actual non-interaction but predicted interaction.
            - False negative: actual interaction but predicted non-interaction.
            """
        )

    with tab4:
        st.subheader("Artesunate SMILES")
        if len(cpi_artesunate_df) > 0:
            st.dataframe(cpi_artesunate_df, use_container_width=True)
            _cpi_download_df(cpi_artesunate_df, "artesunate_smiles_pubchem.csv", "Download Artesunate SMILES")
        else:
            st.warning("Artesunate SMILES file is not available.")

        st.subheader("Candidate protein target template")
        if len(cpi_targets_df) > 0:
            st.dataframe(cpi_targets_df, use_container_width=True)
            _cpi_download_df(cpi_targets_df, "candidate_protein_target_template.csv", "Download candidate target template")
        else:
            st.warning("Candidate protein target template is not available.")

        st.markdown(
            """
            Next step:
            Fill in verified human protein sequences for candidate targets such as SHBG, GDF15, IGF1, and ADIPOQ.
            After protein sequences are available, a future prediction input table can be created using Artesunate SMILES + target protein sequence pairs.
            """
        )

    with tab5:
        st.subheader("CPI / GNN exploration summary report")
        if cpi_summary_text:
            report_view_mode = st.radio(
                "Report display mode",
                ["Readable text", "Rendered markdown"],
                horizontal=True,
                key="cpi_summary_report_view_mode"
            )

            if report_view_mode == "Readable text":
                st.text_area("Full CPI exploration report", value=cpi_summary_text, height=650)
            else:
                st.markdown(cpi_summary_text)

            _cpi_download_text(cpi_summary_text, "cpi_gnn_exploration_summary.md", "Download CPI exploration summary")
        else:
            st.info("CPI exploration summary report is not available.")

        with st.expander("Quick training log", expanded=False):
            if cpi_train_log:
                st.text_area("run_training_quick_log.txt", value=cpi_train_log, height=350)
            else:
                st.info("Quick training log is not available.")

        with st.expander("Quick evaluation log", expanded=False):
            if cpi_eval_log:
                st.text_area("quick_evaluation_log.txt", value=cpi_eval_log, height=350)
            else:
                st.info("Quick evaluation log is not available.")

    with tab6:
        st.subheader("Available CPI / GNN output files")
        st.dataframe(cpi_status_df, use_container_width=True)

        if len(cpi_metrics_df) > 0:
            _cpi_download_df(cpi_metrics_df, "quick_evaluation_metrics.csv", "Download quick evaluation metrics")
        if len(cpi_cm_df) > 0:
            _cpi_download_df(cpi_cm_df, "quick_confusion_matrix.csv", "Download confusion matrix")
        if len(cpi_report_df) > 0:
            _cpi_download_df(cpi_report_df, "quick_classification_report.csv", "Download classification report")
        if len(cpi_predictions_df) > 0:
            _cpi_download_df(cpi_predictions_df, "quick_test_predictions.csv", "Download test predictions")
        if len(cpi_artesunate_df) > 0:
            _cpi_download_df(cpi_artesunate_df, "artesunate_smiles_pubchem.csv", "Download Artesunate SMILES")
        if len(cpi_targets_df) > 0:
            _cpi_download_df(cpi_targets_df, "candidate_protein_target_template.csv", "Download target template")
        if cpi_summary_text:
            _cpi_download_text(cpi_summary_text, "cpi_gnn_exploration_summary.md", "Download CPI summary report")

