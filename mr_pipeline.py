"""
mr_pipeline.py

Generalises the MR pipeline from Python_based_MR_drug_repurposing_pipeline.ipynb
(standardise -> significant-variant filter -> rsID mapping -> LD clumping ->
TwoSampleMR MR analysis) to run against ANY analysis set saved in
analysis_set_record.csv, instead of only the original P1 four-exposure/
one-outcome case study.

-----------------------------------------------------------------------------
ARCHITECTURE -- read this before running anything
-----------------------------------------------------------------------------
Per the P2 decision to keep the R backend in Colab and have the Streamlit
dashboard only read/display results, this module is meant to be imported
and run from a cell in your EXISTING MR pipeline notebook
(Python_based_MR_drug_repurposing_pipeline.ipynb), AFTER your existing R /
rpy2 / TwoSampleMR / ieugwasr / OpenGWAS-JWT setup cells have already run --
NOT from inside the Streamlit app itself. The dashboard's "Backend MR
Results" page just looks for this module's output files on disk.

Usage (from a notebook cell, after your R/rpy2 setup cells):

    import sys
    sys.path.insert(0, "/content/drive/MyDrive/UM_WQF7023/MRDRP-main")
    import mr_pipeline

    # Run one specific saved analysis set:
    summary = mr_pipeline.run_pipeline_for_analysis_set("My_New_Set_01")

    # Or run every saved analysis set that doesn't have results yet:
    overview = mr_pipeline.run_pipeline_for_all_analysis_sets(skip_existing=True)

Outputs are written under:
    backend_work/mr_outputs_by_set/{analysis_set_name}/
        standardised/           -- standardised exposure + outcome files
        clumped/                -- LD-clumped, MR-ready exposure files
        results/                -- per-exposure MR results/harmonised/pleiotropy/heterogeneity
        clumping_summary.csv
        mr_run_summary.csv
        combined_mr_results.csv -- what the dashboard reads

-----------------------------------------------------------------------------
WHAT HAS AND HASN'T BEEN TESTED
-----------------------------------------------------------------------------
The sandbox that wrote this module has no R, no rpy2, and no network access
to Ensembl or OpenGWAS -- so everything that talks to R (ld_clump,
run_mr_for_pair) or to Ensembl (ensure_rsid_column's fallback path) is
UNTESTED against the real thing. It was written to match your notebook's
existing, working calls as closely as possible (same TwoSampleMR.clump_data
parameters: clump_kb=10000, clump_r2=0.001, pop="EUR"; same
read_exposure_data/read_outcome_data/harmonise_data/mr() call shape), but
please treat the first real run as a test, and share the traceback if
something doesn't match your R environment.

Everything else -- column standardisation, significant-variant filtering,
the "already an rsID -> skip the network" fast path, and the file-resolution/
orchestration logic that reads analysis_set_record.csv -- IS covered by
offline unit tests (see the test suite delivered alongside this file) and
should be solid.
"""

from __future__ import annotations

import re
import time
import warnings
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import requests
from scipy.stats import norm

# =============================================================================
# Config / paths -- mirrors app.py's constants so both stay in sync
# =============================================================================

# Same fallback rule as app.py: use the Colab Drive path if present,
# otherwise assume this file sits directly in the project folder (true both
# for a plain `python mr_pipeline.py` run and for wherever the launch
# notebook/script places it on a non-Colab server).
_COLAB_PROJECT_ROOT = Path("/content/drive/MyDrive/UM_WQF7023/MRDRP-main")
if _COLAB_PROJECT_ROOT.exists():
    PROJECT_ROOT = _COLAB_PROJECT_ROOT
else:
    PROJECT_ROOT = Path(__file__).resolve().parent

SCREENING_RECORD_FILE = PROJECT_ROOT / "artesunate_file_screening_record.csv"
ANALYSIS_SET_RECORD_FILE = PROJECT_ROOT / "analysis_set_record.csv"

BACKEND_ROOT = PROJECT_ROOT / "backend_work"
SET_OUTPUT_ROOT = BACKEND_ROOT / "mr_outputs_by_set"

# Same defaults as your existing notebook (Cell 23.5).
CLUMP_KB = 10000
CLUMP_R2 = 0.001
CLUMP_POP = "EUR"
DEFAULT_P_THRESHOLD = 5e-8

ENSEMBL_REST_SERVER = "https://rest.ensembl.org"
ENSEMBL_REQUEST_DELAY_SECONDS = 0.15
ENSEMBL_BATCH_SIZE = 150  # Ensembl's documented cap for POST /vep/human/region is 200; stay safely under it
ENSEMBL_BATCH_DELAY_SECONDS = 1.0


class MrPipelineError(Exception):
    """Raised for pipeline-level problems (missing records, bad inputs)."""


# =============================================================================
# rpy2 / R bridge -- set up lazily, on first use, so this module can still
# be imported (e.g. to run its offline-testable parts) before R is ready.
# =============================================================================

_r_ready = False
robjects = None
pandas2ri = None
TwoSampleMR = None


def _ensure_r_ready():
    global _r_ready, robjects, pandas2ri, TwoSampleMR
    if _r_ready:
        return
    import rpy2.robjects as _robjects
    from rpy2.robjects import pandas2ri as _pandas2ri
    from rpy2.robjects.packages import importr

    _pandas2ri.activate()
    _TwoSampleMR = importr("TwoSampleMR")

    globals()["robjects"] = _robjects
    globals()["pandas2ri"] = _pandas2ri
    globals()["TwoSampleMR"] = _TwoSampleMR
    _r_ready = True


def _r_to_pandas(r_obj):
    _ensure_r_ready()
    with (robjects.default_converter + pandas2ri.converter).context():
        return robjects.conversion.get_conversion().rpy2py(r_obj)


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name))


def _cached_clumped_exposure_path(clumped_dir: Path, exp_file_name: str, p_threshold: float) -> Path:
    """
    Cache filename includes p_threshold so runs at different thresholds
    never collide -- e.g. re-running the same set at 5e-8 vs 1e-5 correctly
    produces (and checks for) two separate cache entries.
    """
    return clumped_dir / f"{_safe_name(exp_file_name)}_p{p_threshold:.0e}_clumped.csv"


def _load_cached_clumped_exposure(cache_path: Path, source_path: Path) -> Optional[pd.DataFrame]:
    """
    Returns the cached clumped DataFrame if `cache_path` exists AND is not
    older than `source_path` (so re-saving/re-fetching the exposure file
    correctly invalidates the cache rather than silently serving stale
    results). Returns None if no valid cache is available, for any reason
    (missing, stale, or unreadable) -- callers should just fall through to
    the normal (slower) processing path in that case.

    Confirmed 2026-08-13 as worth adding: standardise -> filter -> Ensembl
    rsID mapping -> LD clumping was being redone from scratch on every
    single run of the same analysis set, even when testing something else
    entirely (e.g. outcome-matching or a downstream dashboard change) with
    an exposure file that hadn't changed at all -- for an exposure needing
    dozens of per-row Ensembl lookups, that's minutes of unnecessary work
    repeated on every test run.
    """
    if not cache_path.exists():
        return None
    try:
        if cache_path.stat().st_mtime < source_path.stat().st_mtime:
            return None
    except OSError:
        return None
    try:
        return pd.read_csv(cache_path)
    except Exception:
        return None


# =============================================================================
# File reading (matches app.py / the notebook's separator-by-extension rule)
# =============================================================================

def infer_separator(file_path: Path) -> str:
    name = file_path.name.lower()
    if name.endswith(".csv") or name.endswith(".csv.gz"):
        return ","
    return "\t"


def read_gwas_file(file_path: Path, nrows: Optional[int] = None) -> pd.DataFrame:
    return pd.read_csv(
        file_path,
        sep=infer_separator(file_path),
        compression="infer",
        nrows=nrows,
        low_memory=False,
    )


# =============================================================================
# Column standardisation -- same candidate lists as your notebook's
# detect_columns()/COLUMN_CANDIDATES (Cell 5), so anything that already
# passed your screening pages should standardise cleanly here too.
# =============================================================================

COLUMN_CANDIDATES = {
    "SNP": ["SNP", "rsid", "rsID", "RSID", "variant_id", "variant", "MarkerName", "marker", "ID", "hm_rsid"],
    "CHR": ["CHR", "CHROM", "chromosome", "chrom", "hm_chrom", "seqnames"],
    "POS": ["POS", "BP", "base_pair_location", "position", "hm_pos", "pos", "variant_pos", "base_pair_position"],
    "EA": ["EA", "effect_allele", "effectAllele", "A1", "ALT", "alt", "tested_allele", "hm_effect_allele"],
    "OA": ["OA", "other_allele", "otherAllele", "A2", "REF", "ref", "non_effect_allele", "hm_other_allele"],
    "BETA": ["BETA", "beta", "effect_size", "Effect", "effect", "estimate", "log_odds", "logOR"],
    "OR": ["odds_ratio", "OR", "or", "oddsratio", "OddsRatio"],
    "SE": ["SE", "se", "standard_error", "standard_error_beta", "stderr", "StdErr", "sebeta"],
    "EAF": ["EAF", "eaf", "effect_allele_frequency", "A1FREQ", "AF", "af", "freq", "hm_effect_allele_frequency"],
    "P": ["P", "p", "pval", "p_value", "p-value", "PVAL", "pvalue", "P_VALUE", "PVALUE"],
    "N": ["N", "n", "samplesize", "sample_size", "n_samples", "N_total", "total_sample_size"],
}


def find_column(columns: List[str], candidates: List[str]) -> Optional[str]:
    """Case-insensitive match, same rule as the notebook's find_column()."""
    lower_map = {str(c).lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def detect_columns(columns: List[str]) -> dict:
    return {name: find_column(columns, cands) for name, cands in COLUMN_CANDIDATES.items()}


def clean_chr_value(x):
    if pd.isna(x):
        return np.nan
    x = str(x).replace("chr", "").replace("CHR", "").strip()
    if x in ("X", "x"):
        return 23
    if x in ("Y", "y"):
        return 24
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return np.nan


def se_from_pvalue(beta: pd.Series, p: pd.Series) -> pd.Series:
    """
    Derive standard error from a two-tailed p-value and effect size, for
    files that report beta/OR and p_value but no standard_error column at
    all (confirmed 2026-08-06 against real GWAS Catalog REST API exports --
    e.g. insulin measurement GCST001212/GCST90002240 -- which have beta and
    p_value populated for every row but no SE column). Standard technique:
    for a Wald test, z = beta / SE, and p = 2*(1 - Phi(|z|)), so
    SE = |beta| / Phi^-1(1 - p/2). Exact whenever the reported p-value came
    from a standard Wald test, which is virtually always true for GWAS
    summary statistics.
    """
    p = pd.to_numeric(p, errors="coerce").clip(lower=np.finfo(float).tiny, upper=1.0)
    z = norm.ppf(1 - p / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        se = beta.abs() / z
    return se.replace([np.inf, -np.inf], np.nan)


def p_from_beta_se(beta: pd.Series, se: pd.Series) -> pd.Series:
    """
    Derive a two-tailed p-value from beta and standard error, for files
    that report an effect size and its SE but no p_value column. Exact
    inverse of se_from_pvalue(): z = beta / SE, p = 2*(1 - Phi(|z|)).

    Deliberately NOT implemented in the other direction (deriving beta from
    SE + p_value): p is symmetric in the sign of z (a two-tailed test can't
    tell you whether the true effect was positive or negative), so that
    derivation could only ever recover |beta|, never its sign -- silently
    guessing the sign would risk flipping the causal direction, which is
    not an acceptable risk for MR. standardise_dataframe() already requires
    a real beta/odds_ratio column for exactly this reason; this function is
    only ever used the safe way round.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        z = beta / se
    p = 2 * (1 - norm.cdf(z.abs()))
    return pd.Series(p, index=beta.index).clip(lower=np.finfo(float).tiny, upper=1.0)


def standardise_dataframe(
    df: pd.DataFrame,
    trait: str,
    role: str,
    source_label: str,
    force_or_to_beta: bool = False,
    allow_pseudo_snp: bool = True,
    snp_override: Optional[pd.Series] = None,
) -> tuple:
    """
    Core of standardise_file(), operating on an already-loaded DataFrame
    instead of a file path -- shared by standardise_file() (file-based) and
    fetch_outcome_for_instruments() (in-memory, for a small matched subset).

    snp_override: if given, used as the SNP column directly (aligned by
    position/index with `df`) instead of detecting/deriving one from `df`'s
    own columns -- used when the caller already knows the correct rsID for
    each row (e.g. from matching against exposure instruments by position).

    Returns (standardised_df, info_dict) -- same info_dict shape as
    standardise_file()'s return value, minus the file-path keys.
    """
    detected = detect_columns(df.columns.tolist())

    has_beta = detected["BETA"] is not None
    has_or = detected["OR"] is not None
    if not has_beta and not has_or:
        raise MrPipelineError(f"No BETA or odds_ratio column found in {source_label}.")

    # SE and P can each be derived from the other + the effect size when
    # exactly one of them is missing -- see se_from_pvalue()/p_from_beta_se().
    # If BOTH are missing, neither derivation is possible.
    se_derivable = detected["SE"] is None and detected["P"] is not None
    p_derivable = detected["P"] is None and detected["SE"] is not None

    missing_basic = [k for k in ["EA", "OA"] if detected[k] is None]
    if detected["SE"] is None and not se_derivable:
        missing_basic.append("SE")
    if detected["P"] is None and not p_derivable:
        missing_basic.append("P")
    if missing_basic:
        raise MrPipelineError(f"Missing required columns {missing_basic} in {source_label}.")

    out = pd.DataFrame(index=df.index)
    out["CHR"] = df[detected["CHR"]].apply(clean_chr_value) if detected["CHR"] else np.nan
    out["POS"] = pd.to_numeric(df[detected["POS"]], errors="coerce") if detected["POS"] else np.nan
    out["EA"] = df[detected["EA"]].astype(str).str.upper().str.strip()
    out["OA"] = df[detected["OA"]].astype(str).str.upper().str.strip()

    if snp_override is not None:
        out["SNP"] = snp_override.astype(str).str.strip().values
        snp_source_type = "matched_from_exposure_instrument"
    elif detected["SNP"] is not None:
        out["SNP"] = df[detected["SNP"]].astype(str).str.strip()
        snp_source_type = "detected_snp_column"
    elif allow_pseudo_snp and detected["CHR"] is not None and detected["POS"] is not None:
        out["SNP"] = (
            out["CHR"].astype("Int64").astype(str) + ":" + out["POS"].astype("Int64").astype(str)
            + ":" + out["EA"].astype(str) + ":" + out["OA"].astype(str)
        )
        snp_source_type = "pseudo_chr_pos_allele_id"
    else:
        raise MrPipelineError(f"No SNP/rsID column (and no CHR+POS fallback) in {source_label}.")

    if has_beta and not force_or_to_beta:
        out["BETA"] = pd.to_numeric(df[detected["BETA"]], errors="coerce")
        effect_size_type = "beta"
    else:
        out["BETA"] = np.log(pd.to_numeric(df[detected["OR"]], errors="coerce"))
        effect_size_type = "odds_ratio_converted_to_beta"

    if detected["P"] is not None and detected["SE"] is not None:
        out["P"] = pd.to_numeric(df[detected["P"]], errors="coerce")
        out["SE"] = pd.to_numeric(df[detected["SE"]], errors="coerce")
        p_source_type = "detected_p_column"
        se_source_type = "detected_se_column"
    elif detected["P"] is not None and detected["SE"] is None:
        out["P"] = pd.to_numeric(df[detected["P"]], errors="coerce")
        out["SE"] = se_from_pvalue(out["BETA"], out["P"])
        p_source_type = "detected_p_column"
        se_source_type = "derived_from_pvalue"
    elif detected["P"] is None and detected["SE"] is not None:
        out["SE"] = pd.to_numeric(df[detected["SE"]], errors="coerce")
        out["P"] = p_from_beta_se(out["BETA"], out["SE"])
        p_source_type = "derived_from_beta_se"
        se_source_type = "detected_se_column"
    else:
        # Unreachable -- the missing_basic check above already raised when
        # neither derivation is possible.
        raise MrPipelineError(f"Both P and SE are missing in {source_label}, and neither can be derived without the other.")

    out["EAF"] = pd.to_numeric(df[detected["EAF"]], errors="coerce") if detected["EAF"] else np.nan
    out["N"] = pd.to_numeric(df[detected["N"]], errors="coerce") if detected["N"] else np.nan
    out["trait"] = trait
    out["role"] = role
    out["source_file"] = source_label
    out["effect_size_type"] = effect_size_type
    out["snp_source_type"] = snp_source_type
    out["se_source_type"] = se_source_type
    out["p_source_type"] = p_source_type

    out = out.replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=["SNP", "EA", "OA", "BETA", "SE", "P"])

    valid_alleles = {"A", "C", "G", "T"}
    out = out[out["EA"].isin(valid_alleles) & out["OA"].isin(valid_alleles)]
    out = out[out["EA"] != out["OA"]]
    out = out[(out["P"] > 0) & (out["P"] <= 1)]

    info = {
        "trait": trait, "role": role,
        "rows": len(out), "effect_size_type": effect_size_type,
        "snp_source_type": snp_source_type, "se_source_type": se_source_type,
        "p_source_type": p_source_type,
    }
    return out, info


def standardise_file(
    input_path: Path,
    output_path: Path,
    trait: str,
    role: str,
    force_or_to_beta: bool = False,
    allow_pseudo_snp: bool = True,
) -> dict:
    """
    Standardise one GWAS file into columns SNP, CHR, POS, EA, OA, BETA, SE,
    EAF, P, N (+ trait/role/source_file/effect_size_type/snp_source_type
    metadata). Same logic as standardise_gwas_file() in the notebook, but
    generalised (no hardcoded trait names).

    If no rsID/SNP-like column is found but CHR+POS are available, falls
    back to a pseudo ID "CHR:POS:EA:OA" (allow_pseudo_snp=True, the
    notebook's default) -- fine for LD-clumping-free coordinate matching,
    but real rsID is required for TwoSampleMR.clump_data() later, so a
    pseudo-ID exposure will fail at the clumping step with a clear error
    rather than silently producing wrong results.
    """
    df = read_gwas_file(input_path)
    out, info = standardise_dataframe(
        df, trait=trait, role=role, source_label=input_path.name,
        force_or_to_beta=force_or_to_beta, allow_pseudo_snp=allow_pseudo_snp,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    return {
        "trait": info["trait"], "role": info["role"],
        "input_file": str(input_path), "output_file": str(output_path),
        "rows": info["rows"], "effect_size_type": info["effect_size_type"],
        "snp_source_type": info["snp_source_type"], "se_source_type": info["se_source_type"],
        "p_source_type": info["p_source_type"],
    }


def filter_significant(df: pd.DataFrame, p_threshold: float = DEFAULT_P_THRESHOLD) -> pd.DataFrame:
    """
    Keep rows with p < p_threshold. Safe to call even if the input is
    already pre-filtered (e.g. files saved from the GWAS Catalog Search
    page, which are already p<5e-8) -- re-filtering an already-filtered
    file at the same threshold is a no-op.
    """
    return df[pd.to_numeric(df["P"], errors="coerce") < p_threshold].copy()


# =============================================================================
# rsID mapping -- "already an rsID" is the fast, common path (true for
# every file the GWAS Catalog Search / FTP pages save); Ensembl lookup by
# position is the slow fallback for older coordinate-only files.
# =============================================================================

def _query_ensembl_by_position(chrom, pos, max_retries: int = 3) -> list:
    chrom = str(chrom).replace("chr", "").strip()
    try:
        pos = int(pos)
    except (TypeError, ValueError):
        return []

    url = f"{ENSEMBL_REST_SERVER}/overlap/region/human/{chrom}:{pos}-{pos}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, params={"feature": "variation"}, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(1 + attempt)
                continue
            return []
        except requests.RequestException:
            time.sleep(1 + attempt)
    return []


def _best_rsid_from_records(records: Optional[list]) -> Optional[str]:
    for rec in records or []:
        vid = str(rec.get("id", ""))
        if vid.startswith("rs"):
            return vid
    return None


def _query_ensembl_batch_by_position(positions: list, max_retries: int = 2) -> dict:
    """
    Look up rsIDs for MULTIPLE (chrom, pos) positions in ONE HTTP request via
    Ensembl's POST /vep/human/region endpoint (documented max 200 variants
    per call -- see ENSEMBL_BATCH_SIZE), instead of one GET request per
    position. Confirmed 2026-08-07 as the fix for a real case: a ~450-row
    exposure file with no native rsIDs was taking many silent minutes
    (~450 sequential GET requests, each up to 20s timeout x 3 retries if
    Ensembl was slow/rate-limiting) at the per-row ensure_rsid_column()
    step, well before ever reaching LD clumping.

    `positions` is a list of (chrom, pos) tuples. Returns {(chrom, pos):
    rsid_or_None}. Raises on any network/format problem the caller should
    treat as "batch lookup unavailable, fall back to per-row" -- this
    function is deliberately strict (no silent partial results) so a
    malformed response can never be mistaken for "no matches found".

    Variant format sent is VCF-style "CHROM POS . REF ALT . . ." (ID left
    as "." since that's what we're trying to find; REF/ALT don't affect
    which variants Ensembl reports as colocated at that position, only
    which are flagged as matching alleles, and rsid lookup only needs the
    colocated_variants list regardless of exact allele match).
    """
    if not positions:
        return {}

    variant_strings = [f"{chrom} {int(pos)} . N N . . ." for chrom, pos in positions]
    url = f"{ENSEMBL_REST_SERVER}/vep/human/region"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    last_exception = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                url, headers=headers, json={"variants": variant_strings}, timeout=30,
            )
        except requests.RequestException as e:
            last_exception = e
            time.sleep(1 + attempt)
            continue

        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(1 + attempt)
            continue
        if resp.status_code != 200:
            raise MrPipelineError(f"Ensembl batch VEP endpoint returned {resp.status_code}: {resp.text[:200]}")

        try:
            results = resp.json()
        except ValueError as e:
            raise MrPipelineError(f"Ensembl batch VEP response was not valid JSON: {e}") from e

        if not isinstance(results, list) or len(results) != len(positions):
            raise MrPipelineError(
                f"Ensembl batch VEP response shape unexpected (expected a list of "
                f"{len(positions)}, got {type(results).__name__} of "
                f"{len(results) if isinstance(results, list) else 'n/a'})"
            )

        # Match results back to positions by parsed "input" field rather
        # than assuming the response preserves request order -- safer, and
        # falls back to positional index only if "input" is unparseable.
        by_input: dict = {}
        for i, item in enumerate(results):
            if not isinstance(item, dict):
                raise MrPipelineError(f"Ensembl batch VEP result #{i} was not a JSON object.")
            input_str = str(item.get("input", ""))
            parts = input_str.split()
            if len(parts) >= 2:
                try:
                    by_input[(parts[0], int(parts[1]))] = item
                except ValueError:
                    pass

        out = {}
        for i, (chrom, pos) in enumerate(positions):
            item = by_input.get((str(chrom), int(pos)))
            if item is None:
                item = results[i] if i < len(results) and isinstance(results[i], dict) else {}
            colocated = item.get("colocated_variants") or []
            out[(chrom, pos)] = _best_rsid_from_records(colocated)
        return out

    raise MrPipelineError(f"Ensembl batch VEP endpoint failed after {max_retries} attempt(s): {last_exception}")


def ensure_rsid_column(df: pd.DataFrame, use_ensembl_fallback: bool = True, progress_callback=None) -> pd.DataFrame:
    """
    Adds an 'rsid' column. Rows whose SNP is already an rsID (starts with
    "rs") are used as-is, with NO network call -- this covers essentially
    every file saved via the GWAS Catalog Search page, since variant_id
    there already IS the rsID. Rows without a real rsID and without
    use_ensembl_fallback are left unmapped (rsid=None).

    With the fallback enabled, remaining rows are looked up by CHR:POS
    against Ensembl one request at a time (see _query_ensembl_by_position(),
    the position-only /overlap/region endpoint -- allele-agnostic, no
    guessing required). A batched approach via Ensembl's VEP endpoint was
    tried and reverted: confirmed 2026-08-13 on a real run that it silently
    returned a 0% match rate (0/2, 0/47, 0/37 across three batches of
    different sizes) despite the HTTP calls succeeding -- VEP is
    allele-aware, and the placeholder alleles used for the batch query
    don't correspond to real variants, which appears to suppress
    colocated_variants entirely rather than erroring (so the existing
    per-row fallback never even triggered). Reverting to per-row trades
    speed for correctness until the batch approach can be fixed and
    verified against the live API.

    progress_callback, if given, is called as progress_callback(fraction,
    message) -- fraction in [0, 1] -- after every row of the Ensembl
    lookup loop, so a caller running this in the background (e.g. the
    dashboard's one-click MR run) can show real "23/47 mapped" progress
    instead of the process just looking stuck for however long this takes.
    """
    df = df.copy()
    n = len(df)
    rsids: List[Optional[str]] = [None] * n
    statuses: List[str] = [""] * n
    needs_lookup_idx: List[int] = []

    for i in range(n):
        snp = str(df.iloc[i].get("SNP", ""))
        if snp.startswith("rs"):
            rsids[i] = snp
            statuses[i] = "already_rsid"
            continue

        chrom, pos = df.iloc[i].get("CHR"), df.iloc[i].get("POS")
        if pd.isna(chrom) or pd.isna(pos):
            statuses[i] = "missing_chr_pos"
            continue

        if not use_ensembl_fallback:
            statuses[i] = "not_mapped_fallback_disabled"
            continue

        needs_lookup_idx.append(i)

    if needs_lookup_idx:
        print(f"Mapping {len(needs_lookup_idx)} variant(s) to rsIDs via Ensembl (one at a time)...")
        for n_done, i in enumerate(needs_lookup_idx, start=1):
            chrom, pos = df.iloc[i]["CHR"], df.iloc[i]["POS"]
            records = _query_ensembl_by_position(chrom, pos)
            rsid = _best_rsid_from_records(records)
            rsids[i] = rsid
            statuses[i] = "mapped_by_chr_pos" if rsid else "not_mapped"
            if progress_callback is not None:
                progress_callback(
                    n_done / len(needs_lookup_idx),
                    f"mapping rsIDs via Ensembl ({n_done}/{len(needs_lookup_idx)})",
                )
            if n_done % 20 == 0 or n_done == len(needs_lookup_idx):
                print(f"  ... {n_done}/{len(needs_lookup_idx)} done")
            time.sleep(ENSEMBL_REQUEST_DELAY_SECONDS)

        n_mapped = sum(1 for s in statuses if s.startswith("mapped_by_chr_pos"))
        print(f"Ensembl mapping complete: {n_mapped}/{len(needs_lookup_idx)} variant(s) successfully mapped to an rsID.")

    df["rsid"] = rsids
    df["rsid_mapping_status"] = statuses
    return df


# =============================================================================
# Targeted outcome fetch -- downloads the FULL (not p-value-filtered) FTP
# file for an outcome accession and matches it against a specific set of
# exposure instruments by genomic position, rather than re-mapping rsIDs for
# the whole file. This is the correct way to build outcome data for MR:
# the outcome must be looked up at the exposure's instrument SNPs
# regardless of the outcome's own significance -- using a p-value-filtered
# "significant variants" file for the outcome role (e.g. one saved from the
# GWAS Catalog Search dashboard page) will systematically miss almost every
# instrument, since a SNP being both exposure-significant AND independently
# outcome-significant is the rare exception, not the norm. Confirmed
# 2026-07-27: doing this produced "No SNPs specified for the exposure are
# present in the outcome dataset" for every exposure in a real run.
# =============================================================================

def _match_instruments_in_local_file(
    local_path: Path,
    instrument_df: pd.DataFrame,
    chunksize: int = 200_000,
) -> pd.DataFrame:
    """
    Scan a local (possibly large) GWAS summary-stats file in chunks and
    return the rows matching instrument_df's CHR+POS, with a
    '_matched_snp' column carrying the corresponding instrument's SNP
    identifier. Empty DataFrame if no chromosome/position columns are
    found in the file, or if nothing matches -- callers treat both as
    "this file isn't usable/adequate", not as an error.

    If MULTIPLE instrument rows share the exact same CHR+POS (this happens
    when two different exposures' clumped instruments land on the same
    variant -- plausible for biologically related traits), every one of
    them gets its own output row tagged with its own SNP identifier, all
    sharing the same underlying outcome statistics. A plain dict keyed by
    position would silently keep only the last one and drop the rest --
    confirmed 2026-07-27 as the cause of a real run where an exposure with
    valid, position-matching instruments was incorrectly skipped with "No
    matching outcome data found".
    """
    wanted = instrument_df[["SNP", "CHR", "POS"]].copy()
    wanted["CHR"] = wanted["CHR"].apply(clean_chr_value)
    wanted["POS"] = pd.to_numeric(wanted["POS"], errors="coerce")
    wanted = wanted.dropna(subset=["CHR", "POS"])
    if len(wanted) == 0:
        return pd.DataFrame()

    wanted_lookup: dict = {}
    for chrom, pos, snp in zip(wanted["CHR"], wanted["POS"], wanted["SNP"]):
        wanted_lookup.setdefault((chrom, pos), []).append(snp)

    sep = infer_separator(local_path)
    header = pd.read_csv(local_path, sep=sep, compression="infer", nrows=5)
    if header.shape[1] <= 1:
        sep = "," if sep == "\t" else "\t"
        header = pd.read_csv(local_path, sep=sep, compression="infer", nrows=5)

    detected = detect_columns(header.columns.tolist())
    chr_col, pos_col = detected["CHR"], detected["POS"]
    if not chr_col or not pos_col:
        return pd.DataFrame()

    matched_chunks = []
    rows_scanned = 0
    reader = pd.read_csv(local_path, sep=sep, compression="infer", chunksize=chunksize, low_memory=False)
    for chunk_idx, chunk in enumerate(reader):
        rows_scanned += len(chunk)
        chunk_chr = chunk[chr_col].apply(clean_chr_value)
        chunk_pos = pd.to_numeric(chunk[pos_col], errors="coerce")
        keys = list(zip(chunk_chr, chunk_pos))

        row_positions = []
        matched_snps = []
        for row_pos, key in enumerate(keys):
            snps_here = wanted_lookup.get(key)
            if snps_here:
                for snp in snps_here:
                    row_positions.append(row_pos)
                    matched_snps.append(snp)

        if row_positions:
            matched = chunk.iloc[row_positions].copy()
            matched["_matched_snp"] = matched_snps
            matched_chunks.append(matched)
        if (chunk_idx + 1) % 20 == 0:
            n_matched_so_far = sum(len(c) for c in matched_chunks)
            print(f"  ... scanned {rows_scanned:,} rows, matched {n_matched_so_far} so far")

    if not matched_chunks:
        return pd.DataFrame()

    return pd.concat(matched_chunks, ignore_index=True)


def try_local_outcome_file(
    outcome_path: Path,
    outcome_trait: str,
    instrument_df: pd.DataFrame,
    chunksize: int = 200_000,
) -> pd.DataFrame:
    """
    Try to build outcome data directly from an already-saved local file, with
    NO network fetch at all -- fast, and correct as long as that file isn't
    p-value-filtered to its own significant hits (true for outcome files
    saved via the GWAS Catalog Search page now that it skips p-value
    filtering for the outcome role). Returns an EMPTY DataFrame if the file
    doesn't cover the given instruments (e.g. an older, still p-filtered
    save) -- callers should treat that as "fall back to a fresh fetch", not
    as an error; this function never raises for a simple non-match.
    """
    matched_raw_df = _match_instruments_in_local_file(outcome_path, instrument_df, chunksize=chunksize)
    if len(matched_raw_df) == 0:
        return pd.DataFrame()

    std_df, info = standardise_dataframe(
        matched_raw_df.drop(columns=["_matched_snp"]),
        trait=outcome_trait, role="outcome", source_label=f"{outcome_path.name} (local, position-matched)",
        snp_override=matched_raw_df["_matched_snp"],
    )
    print(
        f"Using the already-saved outcome file directly -- matched {len(std_df)} / "
        f"{len(instrument_df)} instrument(s), no download needed. "
        f"effect_size_type={info['effect_size_type']}"
    )
    return std_df


def fetch_outcome_for_instruments(
    outcome_accession: str,
    outcome_trait: str,
    instrument_df: pd.DataFrame,
    work_dir: Optional[Path] = None,
    keep_downloaded_file: bool = False,
    chunksize: int = 200_000,
    debug: bool = False,
) -> pd.DataFrame:
    """
    Download the outcome accession's full FTP file (via gwas_catalog_ftp,
    same build-preference logic as the dashboard's FTP path -- prefers a
    raw build-tagged file, falls back to the harmonised/ pipeline, falls
    back to a plain raw file) and keep only the rows matching
    `instrument_df`'s CHR+POS (the LD-clumped exposure instruments).
    Matched rows are assigned the exposure's own SNP identifier directly
    (no separate rsID lookup needed for the outcome side at all).

    This always re-downloads -- prefer try_local_outcome_file() first if an
    already-saved local copy might already be adequate, to avoid the
    network round-trip.

    Returns a standardised (SNP/CHR/POS/EA/OA/BETA/SE/EAF/P/N) DataFrame
    ready for TwoSampleMR.read_outcome_data(), containing at most
    len(instrument_df) rows.
    """
    try:
        import gwas_catalog_ftp
    except ImportError as e:
        raise MrPipelineError(
            "gwas_catalog_ftp.py is required for fetch_outcome_for_instruments() but wasn't "
            "found next to mr_pipeline.py. Make sure it's in the same folder."
        ) from e

    best = gwas_catalog_ftp.find_best_available_file(outcome_accession, debug=debug)
    if best is None:
        raise MrPipelineError(
            f"No usable file found on the FTP archive for outcome accession {outcome_accession}."
        )

    work_dir = work_dir or (PROJECT_ROOT / "_mr_outcome_downloads")
    work_dir.mkdir(parents=True, exist_ok=True)
    local_path = work_dir / best["filename"]

    size_note = f", size: {best['size_str']}" if best.get("size_str") else ""
    print(
        f"Fetching outcome data for {outcome_accession} ({outcome_trait}) to match "
        f"{len(instrument_df)} instrument(s) -- build: {best['build']}, source: {best['source']}{size_note}"
    )

    t0 = time.time()
    gwas_catalog_ftp.download_file(best["url"], local_path)
    print(f"Downloaded in {time.time() - t0:.1f}s, scanning for instrument positions...")

    try:
        matched_raw_df = _match_instruments_in_local_file(local_path, instrument_df, chunksize=chunksize)
    finally:
        if not keep_downloaded_file:
            try:
                local_path.unlink(missing_ok=True)
            except OSError:
                pass

    if len(matched_raw_df) == 0:
        print(f"WARNING: none of the {len(instrument_df)} instrument position(s) were found in the outcome file.")
        return pd.DataFrame()

    print(f"Matched {len(matched_raw_df)} / {len(instrument_df)} instrument(s) in the outcome data by position.")

    std_df, info = standardise_dataframe(
        matched_raw_df.drop(columns=["_matched_snp"]),
        trait=outcome_trait, role="outcome", source_label=f"{outcome_accession} (position-matched)",
        snp_override=matched_raw_df["_matched_snp"],
    )
    print(f"Outcome adaptation: effect_size_type={info['effect_size_type']}, snp_source_type={info['snp_source_type']}")

    return std_df


# =============================================================================
# LD clumping -- remote clumping via TwoSampleMR.clump_data() / the
# OpenGWAS API, same parameters as the notebook. No local reference panel
# needed, but OPENGWAS_JWT must already be set as an environment variable
# (same as your notebook's Cell 23.5A) before calling this.
# =============================================================================

def ld_clump(
    df: pd.DataFrame,
    id_label: str,
    clump_kb: int = CLUMP_KB,
    clump_r2: float = CLUMP_R2,
    pop: str = CLUMP_POP,
) -> pd.DataFrame:
    """
    LD-clump `df` (must already have an 'rsid' column, from
    ensure_rsid_column(), and a 'P' column). Returns the subset of `df`
    whose rsid survived clumping, with ALL of df's original columns kept
    (not just TwoSampleMR's clump_data output columns).
    """
    _ensure_r_ready()

    import os
    if not os.environ.get("OPENGWAS_JWT", "").strip():
        raise MrPipelineError(
            "OPENGWAS_JWT is not set. Run your OpenGWAS token cell (same as Cell 23.5A "
            "in the MR pipeline notebook) before calling ld_clump()."
        )

    clumpable = df.dropna(subset=["rsid", "P"]).copy()
    clumpable = clumpable[clumpable["rsid"].astype(str).str.startswith("rs")]
    if len(clumpable) == 0:
        return df.iloc[0:0].copy()

    clump_input = pd.DataFrame({
        "SNP": clumpable["rsid"].astype(str),
        "pval.exposure": pd.to_numeric(clumpable["P"], errors="coerce"),
        "id.exposure": id_label,
        "exposure": id_label,
    }).dropna(subset=["SNP", "pval.exposure"])

    if len(clump_input) == 0:
        return df.iloc[0:0].copy()

    with (robjects.default_converter + pandas2ri.converter).context():
        r_clump_input = robjects.conversion.get_conversion().py2rpy(clump_input)

    clumped_r = TwoSampleMR.clump_data(r_clump_input, clump_kb=clump_kb, clump_r2=clump_r2, pop=pop)
    clumped_df = _r_to_pandas(clumped_r)

    if len(clumped_df) == 0:
        return df.iloc[0:0].copy()

    kept_rsids = set(clumped_df["SNP"].astype(str).tolist())
    return clumpable[clumpable["rsid"].astype(str).isin(kept_rsids)].copy()


# =============================================================================
# MR analysis for one exposure-outcome pair (same call shape as the
# notebook's Cell 15 / Cell 20)
# =============================================================================

def run_mr_for_pair(exposure_file: Path, outcome_file: Path, exposure_label: str, outcome_label: str) -> dict:
    """
    Run TwoSampleMR's read -> harmonise -> mr() flow for ONE exposure file
    against ONE outcome file. Both files should already be standardised
    (SNP/CHR/POS/EA/OA/BETA/SE/EAF/P/N columns) with SNP holding real
    rsIDs -- i.e. exposure_file should be the LD-clumped, rsid-mapped
    subset written by run_pipeline_for_analysis_set().

    Returns a dict with keys: status ("success"/"failed"), error,
    mr_results, harmonised, pleiotropy, heterogeneity (DataFrames, some
    empty on failure/partial failure).
    """
    _ensure_r_ready()
    empty = pd.DataFrame()
    try:
        exp_dat = TwoSampleMR.read_exposure_data(
            filename=str(exposure_file), sep=",",
            snp_col="SNP", beta_col="BETA", se_col="SE",
            effect_allele_col="EA", other_allele_col="OA",
            eaf_col="EAF", pval_col="P", samplesize_col="N",
            chr_col="CHR", pos_col="POS", clump=False,
        )

        exp_df = pd.read_csv(exposure_file)
        snp_list = robjects.StrVector(exp_df["SNP"].dropna().astype(str).tolist())

        outcome_dat = TwoSampleMR.read_outcome_data(
            snps=snp_list, filename=str(outcome_file), sep=",",
            snp_col="SNP", beta_col="BETA", se_col="SE",
            effect_allele_col="EA", other_allele_col="OA",
            eaf_col="EAF", pval_col="P",
        )

        harmonised = TwoSampleMR.harmonise_data(exp_dat, outcome_dat)
        harmonised_py = _r_to_pandas(harmonised)

        if len(harmonised_py) == 0:
            return {"status": "failed", "error": "No SNPs retained after harmonisation.",
                    "mr_results": empty, "harmonised": harmonised_py, "pleiotropy": empty, "heterogeneity": empty}

        res = TwoSampleMR.mr(harmonised)
        res_py = _r_to_pandas(res)
        res_py["exposure_label"] = exposure_label
        res_py["outcome_label"] = outcome_label

        try:
            pleiotropy_py = _r_to_pandas(TwoSampleMR.mr_pleiotropy_test(harmonised))
        except Exception as e:
            pleiotropy_py = pd.DataFrame({"warning": [str(e)]})

        try:
            heterogeneity_py = _r_to_pandas(TwoSampleMR.mr_heterogeneity(harmonised))
        except Exception as e:
            heterogeneity_py = pd.DataFrame({"warning": [str(e)]})

        return {"status": "success", "error": None, "mr_results": res_py,
                "harmonised": harmonised_py, "pleiotropy": pleiotropy_py, "heterogeneity": heterogeneity_py}

    except Exception as e:
        return {"status": "failed", "error": str(e), "mr_results": empty,
                "harmonised": empty, "pleiotropy": empty, "heterogeneity": empty}


# =============================================================================
# Orchestration: run the whole pipeline for ONE saved analysis set
# =============================================================================

def load_screening_record() -> pd.DataFrame:
    if not SCREENING_RECORD_FILE.exists():
        raise MrPipelineError(f"{SCREENING_RECORD_FILE} not found.")
    return pd.read_csv(SCREENING_RECORD_FILE)


def load_analysis_set_record() -> pd.DataFrame:
    if not ANALYSIS_SET_RECORD_FILE.exists():
        raise MrPipelineError(f"{ANALYSIS_SET_RECORD_FILE} not found.")
    return pd.read_csv(ANALYSIS_SET_RECORD_FILE)


def resolve_file_path(screening_df: pd.DataFrame, file_name: str) -> Path:
    matches = screening_df[screening_df["file_name"].astype(str) == str(file_name)]
    if len(matches) == 0:
        raise MrPipelineError(f"'{file_name}' not found in the screening record.")
    return Path(matches.iloc[-1]["file_path"])


def get_analysis_set_row(analysis_set_name: str) -> pd.Series:
    sets_df = load_analysis_set_record()
    matches = sets_df[sets_df["analysis_set_name"].astype(str) == str(analysis_set_name)]
    if len(matches) == 0:
        raise MrPipelineError(f"Analysis set '{analysis_set_name}' not found in {ANALYSIS_SET_RECORD_FILE}.")
    return matches.iloc[-1]


def set_output_dir(analysis_set_name: str) -> Path:
    return SET_OUTPUT_ROOT / _safe_name(analysis_set_name)


def _parse_gcst_accession(file_name: str) -> Optional[str]:
    """Extract a leading 'GCSTnnnnnnnn' accession from a filename, if present."""
    m = re.match(r"^(GCST\d+)", str(file_name))
    return m.group(1) if m else None


def run_pipeline_for_analysis_set(
    analysis_set_name: str,
    p_threshold: float = DEFAULT_P_THRESHOLD,
    use_ensembl_fallback: bool = True,
    use_cache: bool = True,
    progress_callback=None,
) -> dict:
    """
    Full pipeline for ONE saved analysis set, in two passes:

    Pass 1: for each exposure file, standardise -> filter to p < p_threshold
    -> rsID map -> LD clump. With use_cache=True (the default), an exposure
    whose clumped result from a previous run is still up to date (source
    file unchanged since, same p_threshold) is loaded from that cache
    instead of being reprocessed -- this is the expensive step when Ensembl
    fallback is needed, so re-running the same set repeatedly (e.g. while
    testing something downstream) is fast after the first run. Pass
    use_cache=False to force a full recompute (e.g. after fixing something
    upstream of clumping, or if you suspect a stale cache).

    Outcome fetch (once per outcome file, not once per exposure): for EACH
    outcome file in the set -- multiple outcomes are supported, e.g. as a
    hedge against picking a single outcome study that turns out to be too
    narrow/underpowered (confirmed 2026-08-05: a single-gene rare-variant
    burden-test file was mistaken for a genome-wide CAD GWAS, producing
    zero matches for every exposure; a second, larger outcome study in the
    same set would have produced results regardless) -- the clumped
    instruments from ALL exposures are combined and that outcome's FULL
    (not p-value-filtered) FTP file is downloaded ONCE and matched against
    them by genomic position (see fetch_outcome_for_instruments()).

    Backward compatible with sets saved before multi-outcome support: falls
    back to the old singular outcome_file/outcome_trait columns if the new
    plural outcome_files/outcome_traits columns aren't present or are empty.

    Pass 2: every exposure is run against every outcome independently
    (exposures x outcomes). mr_run_summary and combined_results carry
    outcome_file/outcome_trait columns so results from different outcome
    files remain distinguishable even when they share the same trait label.

    Saves everything under set_output_dir(analysis_set_name)/ and returns a
    dict with the same summary tables (also written to disk for the
    dashboard).

    progress_callback, if given, is called as progress_callback(fraction,
    message) throughout the run -- fraction in [0, 1], message a short
    human-readable description of the current step. Intended for a caller
    (e.g. a background subprocess launched by the dashboard's "Run
    analysis" button) to write real progress to a file the UI can poll,
    since a full run of even a small analysis set can take many minutes
    when Ensembl fallback is needed.
    """
    def _report(fraction: float, message: str) -> None:
        if progress_callback is not None:
            try:
                progress_callback(min(max(fraction, 0.0), 1.0), message)
            except Exception:
                pass  # a broken progress reporter should never crash the actual analysis

    _report(0.0, f"Starting analysis set '{analysis_set_name}'")
    set_row = get_analysis_set_row(analysis_set_name)

    exposure_files = [f.strip() for f in str(set_row["exposure_files"]).split(";") if f.strip()]
    if len(exposure_files) == 0:
        raise MrPipelineError(f"Analysis set '{analysis_set_name}' has no exposure files.")

    # New format: outcome_files / outcome_traits (plural, semicolon-joined,
    # same convention as exposure_files/exposure_traits). Falls back to the
    # old singular outcome_file / outcome_trait columns for sets saved
    # before multi-outcome support.
    _outcome_files_raw = str(set_row.get("outcome_files", "")).strip()
    if _outcome_files_raw and _outcome_files_raw.lower() != "nan":
        outcome_files = [f.strip() for f in _outcome_files_raw.split(";") if f.strip()]
        _outcome_traits_raw = str(set_row.get("outcome_traits", "")).strip()
        outcome_traits = (
            [t.strip() for t in _outcome_traits_raw.split(";") if t.strip()]
            if _outcome_traits_raw and _outcome_traits_raw.lower() != "nan" else []
        )
    else:
        _single_outcome_file = str(set_row.get("outcome_file", "")).strip()
        if not _single_outcome_file or _single_outcome_file.lower() == "nan":
            raise MrPipelineError(f"Analysis set '{analysis_set_name}' has no outcome file(s) specified.")
        outcome_files = [_single_outcome_file]
        outcome_traits = [str(set_row.get("outcome_trait", "outcome")).strip()]

    if len(outcome_traits) != len(outcome_files):
        outcome_traits = [
            outcome_traits[i] if i < len(outcome_traits) else outcome_files[i]
            for i in range(len(outcome_files))
        ]

    screening_df = load_screening_record()

    set_dir = set_output_dir(analysis_set_name)
    std_dir = set_dir / "standardised"
    clumped_dir = set_dir / "clumped"
    results_dir = set_dir / "results"
    for d in (std_dir, clumped_dir, results_dir):
        d.mkdir(parents=True, exist_ok=True)

    print(f"Analysis set: {analysis_set_name}")
    print(f"Exposure file(s): {exposure_files}")
    print(f"Outcome file(s): {outcome_files}")

    LOW_INSTRUMENT_COUNT_THRESHOLD = 3  # MR-Egger / weighted median need several SNPs to be meaningful

    # ---- Pass 1: standardise -> filter -> rsID map -> LD clump each exposure ----
    # (Outcome-independent -- unchanged by multi-outcome support.)
    clump_records = []
    mr_ready_exposures = {}  # exp_file_name -> (trait_label, mr_ready_df with SNP=rsid)

    n_exposures = len(exposure_files)
    for exp_idx, exp_file_name in enumerate(exposure_files):
        _report(
            (exp_idx / n_exposures) * 0.7,
            f"Processing exposure {exp_idx + 1}/{n_exposures}: {exp_file_name}",
        )

        def _exposure_sub_progress(sub_fraction: float, message: str) -> None:
            _report(
                ((exp_idx + sub_fraction) / n_exposures) * 0.7,
                f"Exposure {exp_idx + 1}/{n_exposures} ({exp_file_name}): {message}",
            )

        def _ensembl_sub_progress(sub_fraction: float, message: str) -> None:
            # Scaled into [0, 0.85] so it never exceeds the fixed 0.85
            # checkpoint used for "LD clumping" below -- otherwise, since
            # this callback naturally reaches 1.0 when mapping finishes,
            # progress would visibly tick backwards for a moment right as
            # clumping starts.
            _exposure_sub_progress(sub_fraction * 0.85, message)

        trait_label = exp_file_name
        try:
            row_match = screening_df[screening_df["file_name"].astype(str) == exp_file_name]
            if len(row_match) > 0:
                trait_label = str(row_match.iloc[-1].get("trait", exp_file_name))

            exp_path = resolve_file_path(screening_df, exp_file_name)

            cache_path = _cached_clumped_exposure_path(clumped_dir, exp_file_name, p_threshold)
            cached_df = _load_cached_clumped_exposure(cache_path, exp_path) if use_cache else None

            if cached_df is not None:
                print(f"Using cached clumped result for {exp_file_name} (unchanged since last run, p_threshold={p_threshold:.1e}) -- skipping re-processing.")
                _report((exp_idx + 1) / n_exposures * 0.7, f"Exposure {exp_idx + 1}/{n_exposures} ({exp_file_name}): using cached result")
                clump_records.append({
                    "exposure_file": exp_file_name, "trait": trait_label,
                    "status": "success (cached)" if len(cached_df) > 0 else "failed (cached)",
                    "reason": None if len(cached_df) > 0 else "LD clumping returned zero variants (from cache)",
                    "input_variants": None, "clumped_variants": len(cached_df),
                    "effect_size_type": None, "snp_source_type": None,
                    "se_source_type": None, "p_source_type": None,
                    "instrument_note": "Loaded from cache -- source file unchanged since the last run at this p_threshold.",
                })
                if len(cached_df) == 0:
                    continue
                mr_ready_exp = cached_df.copy()
                mr_ready_exp["SNP"] = mr_ready_exp["rsid"]
                mr_ready_exposures[exp_file_name] = (trait_label, mr_ready_exp)
                continue

            _exposure_sub_progress(0.0, "standardising")
            exp_std_path = std_dir / f"{_safe_name(exp_file_name)}_standardised.csv"
            exp_std_record = standardise_file(exp_path, exp_std_path, trait=trait_label, role="exposure")

            std_df = pd.read_csv(exp_std_path)
            sig_df = filter_significant(std_df, p_threshold=p_threshold)

            if len(sig_df) == 0:
                clump_records.append({
                    "exposure_file": exp_file_name, "trait": trait_label, "status": "skipped",
                    "reason": f"No variants below p < {p_threshold:.1e}",
                    "input_variants": 0, "clumped_variants": 0,
                    "effect_size_type": exp_std_record["effect_size_type"],
                    "snp_source_type": exp_std_record["snp_source_type"],
                    "se_source_type": exp_std_record["se_source_type"],
                    "p_source_type": exp_std_record["p_source_type"],
                    "instrument_note": None,
                })
                continue

            mapped_df = ensure_rsid_column(
                sig_df, use_ensembl_fallback=use_ensembl_fallback, progress_callback=_ensembl_sub_progress,
            )
            _exposure_sub_progress(0.85, "LD clumping")
            clumped_df = ld_clump(mapped_df, id_label=trait_label)

            clumped_df.to_csv(cache_path, index=False)

            instrument_note = None
            if 0 < len(clumped_df) < LOW_INSTRUMENT_COUNT_THRESHOLD:
                instrument_note = (
                    f"Only {len(clumped_df)} instrument(s) after clumping -- MR-Egger/weighted-median "
                    "are not meaningful with this few SNPs; TwoSampleMR will fall back to a Wald-ratio-"
                    "style single/few-SNP estimate. Interpret with appropriate caution."
                )

            clump_records.append({
                "exposure_file": exp_file_name, "trait": trait_label,
                "status": "success" if len(clumped_df) > 0 else "failed",
                "reason": None if len(clumped_df) > 0 else "LD clumping returned zero variants",
                "input_variants": int(mapped_df["rsid"].notna().sum()),
                "clumped_variants": len(clumped_df),
                "effect_size_type": exp_std_record["effect_size_type"],
                "snp_source_type": exp_std_record["snp_source_type"],
                "se_source_type": exp_std_record["se_source_type"],
                "p_source_type": exp_std_record["p_source_type"],
                "instrument_note": instrument_note,
            })

            if len(clumped_df) == 0:
                continue

            mr_ready_exp = clumped_df.copy()
            mr_ready_exp["SNP"] = mr_ready_exp["rsid"]
            mr_ready_exposures[exp_file_name] = (trait_label, mr_ready_exp)

        except Exception as e:
            clump_records.append({
                "exposure_file": exp_file_name, "trait": trait_label, "status": "failed",
                "reason": str(e), "input_variants": 0, "clumped_variants": 0,
                "effect_size_type": None, "snp_source_type": None, "se_source_type": None, "p_source_type": None, "instrument_note": None,
            })

    # ---- Fetch each outcome ONCE (not once per exposure), matched against
    #      every exposure's combined instruments ----
    combined_instruments = pd.DataFrame()
    if mr_ready_exposures:
        combined_instruments = pd.concat(
            [df.assign(_source_exposure=name) for name, (_, df) in mr_ready_exposures.items()],
            ignore_index=True,
        )

    outcome_by_pair = {}  # (exp_file_name, outcome_file_name) -> path to matched CSV
    outcome_fetch_notes = {}  # outcome_file_name -> note, if that outcome's fetch had an issue

    if len(combined_instruments) > 0:
        n_outcomes = len(outcome_files)
        for outcome_idx, (outcome_file_name, outcome_trait) in enumerate(zip(outcome_files, outcome_traits)):
            _report(
                0.7 + (outcome_idx / n_outcomes) * 0.15,
                f"Fetching outcome data {outcome_idx + 1}/{n_outcomes}: {outcome_file_name} ({outcome_trait})",
            )
            outcome_accession = _parse_gcst_accession(outcome_file_name)

            # Tier 1: try the already-saved local outcome file first -- fast,
            # no network round-trip.
            matched_outcome_df = pd.DataFrame()
            this_outcome_note = None
            try:
                outcome_path = resolve_file_path(screening_df, outcome_file_name)
                matched_outcome_df = try_local_outcome_file(outcome_path, outcome_trait, combined_instruments)
            except Exception as e:
                print(f"Could not use the saved outcome file '{outcome_file_name}' directly ({e}); will try fetching fresh.")

            # Tier 2: fall back to a fresh FTP fetch if the local file wasn't adequate.
            if len(matched_outcome_df) == 0 and outcome_accession:
                try:
                    matched_outcome_df = fetch_outcome_for_instruments(
                        outcome_accession, outcome_trait, combined_instruments,
                        work_dir=std_dir,
                    )
                except Exception as e:
                    this_outcome_note = f"Targeted outcome fetch failed ({e}); falling back to the saved outcome file's own SNPs as-is."
                    print(f"WARNING [{outcome_file_name}]: {this_outcome_note}")
            elif len(matched_outcome_df) == 0 and not outcome_accession:
                this_outcome_note = (
                    f"The saved outcome file didn't cover the instruments by position, and no GCST "
                    f"accession could be parsed from '{outcome_file_name}' to fetch a fresh copy; "
                    "falling back to the saved outcome file's own SNPs as-is."
                )
                print(f"WARNING [{outcome_file_name}]: {this_outcome_note}")

            if len(matched_outcome_df) > 0:
                for exp_file_name, (trait_label, mr_ready_exp) in mr_ready_exposures.items():
                    this_pair_outcome = matched_outcome_df[
                        matched_outcome_df["SNP"].isin(mr_ready_exp["SNP"])
                    ]
                    if len(this_pair_outcome) == 0:
                        continue
                    out_path = std_dir / f"{_safe_name(exp_file_name)}__{_safe_name(outcome_file_name)}_outcome_matched.csv"
                    this_pair_outcome.to_csv(out_path, index=False)
                    outcome_by_pair[(exp_file_name, outcome_file_name)] = out_path
            else:
                # Tier 3 (last resort) for THIS outcome file specifically:
                # standardise the saved outcome file as-is, using ITS OWN
                # SNP identifiers directly (correct only if that file
                # happens to already cover the right variants).
                #
                # Deliberately use_ensembl_fallback=False here, REGARDLESS
                # of the use_ensembl_fallback argument passed to this whole
                # function: this path standardises the FULL outcome file
                # (now potentially hundreds of thousands of rows, since
                # outcome saves are no longer p-value-filtered), and
                # ensure_rsid_column()'s Ensembl fallback does one network
                # lookup PER ROW with an enforced delay between each --
                # confirmed 2026-08-06 as the actual cause of multi-hour
                # hangs (not the pipeline being fundamentally slow). If the
                # file lacks native rsIDs, this tier should fail fast
                # (rows without a real rsID get dropped below) rather than
                # spend hours Ensembl-mapping a file-wide fallback that
                # Tier 1/Tier 2's position-based matching already covers
                # more reliably.
                try:
                    outcome_path = resolve_file_path(screening_df, outcome_file_name)
                    outcome_std_path = std_dir / f"{_safe_name(outcome_file_name)}_standardised.csv"
                    outcome_std_record = standardise_file(outcome_path, outcome_std_path, trait=outcome_trait, role="outcome")
                    outcome_std_df = pd.read_csv(outcome_std_path)
                    outcome_mapped_df = ensure_rsid_column(outcome_std_df, use_ensembl_fallback=False)
                    outcome_mapped_df["SNP"] = outcome_mapped_df["rsid"]
                    outcome_fallback_path = std_dir / f"{_safe_name(outcome_file_name)}_outcome_mr_ready_fallback.csv"
                    outcome_mapped_df.dropna(subset=["SNP"]).to_csv(outcome_fallback_path, index=False)
                    n_fallback_rows = len(outcome_mapped_df.dropna(subset=["SNP"]))
                    print(
                        f"Fallback outcome adaptation [{outcome_file_name}]: "
                        f"effect_size_type={outcome_std_record['effect_size_type']}, "
                        f"snp_source_type={outcome_std_record['snp_source_type']}, "
                        f"{n_fallback_rows} row(s) with a usable rsID"
                    )
                    if n_fallback_rows == 0:
                        this_outcome_note = (
                            f"Neither position-matching nor the fallback found usable data for "
                            f"'{outcome_file_name}' -- that file likely uses coordinate-only identifiers "
                            "with no rsID, and this last-resort tier does not attempt Ensembl mapping on "
                            "a whole outcome file (too slow at this scale). Consider a different outcome "
                            "study, or check that its build truly matches the exposures."
                        )
                    for exp_file_name in mr_ready_exposures:
                        outcome_by_pair[(exp_file_name, outcome_file_name)] = outcome_fallback_path
                except Exception as e:
                    this_outcome_note = f"{this_outcome_note or ''} Fallback outcome preparation also failed: {e}"
                    print(f"WARNING [{outcome_file_name}]: {this_outcome_note}")

            outcome_fetch_notes[outcome_file_name] = this_outcome_note

    # ---- Pass 2: MR every exposure against every outcome, independently ----
    mr_run_records = []
    all_mr_results = []

    total_pairs = len(mr_ready_exposures) * len(outcome_files) if outcome_files else 0
    pair_idx = 0

    for exp_file_name, (trait_label, mr_ready_exp) in mr_ready_exposures.items():
        for outcome_file_name, outcome_trait in zip(outcome_files, outcome_traits):
            if total_pairs > 0:
                _report(
                    0.85 + (pair_idx / total_pairs) * 0.15,
                    f"Running MR for {trait_label} vs {outcome_trait} (pair {pair_idx + 1}/{total_pairs})",
                )
            pair_idx += 1

            outcome_path_for_pair = outcome_by_pair.get((exp_file_name, outcome_file_name))
            if outcome_path_for_pair is None:
                mr_run_records.append({
                    "exposure_file": exp_file_name, "trait": trait_label,
                    "outcome_file": outcome_file_name, "outcome_trait": outcome_trait,
                    "status": "skipped",
                    "error": outcome_fetch_notes.get(outcome_file_name) or "No matching outcome data found for this exposure's instruments.",
                    "harmonised_snps": 0,
                })
                continue

            mr_ready_exp_path = clumped_dir / f"{_safe_name(exp_file_name)}_mr_ready.csv"
            mr_ready_exp.to_csv(mr_ready_exp_path, index=False)

            mr_out = run_mr_for_pair(
                mr_ready_exp_path, outcome_path_for_pair,
                exposure_label=trait_label, outcome_label=outcome_trait,
            )

            safe_pair_name = f"{_safe_name(exp_file_name)}__{_safe_name(outcome_file_name)}"
            mr_out["mr_results"].to_csv(results_dir / f"{safe_pair_name}_mr_results.csv", index=False)
            mr_out["harmonised"].to_csv(results_dir / f"{safe_pair_name}_harmonised.csv", index=False)
            mr_out["pleiotropy"].to_csv(results_dir / f"{safe_pair_name}_pleiotropy.csv", index=False)
            mr_out["heterogeneity"].to_csv(results_dir / f"{safe_pair_name}_heterogeneity.csv", index=False)

            if mr_out["status"] == "success":
                result_with_outcome_file = mr_out["mr_results"].copy()
                result_with_outcome_file["outcome_file"] = outcome_file_name
                all_mr_results.append(result_with_outcome_file)

            mr_run_records.append({
                "exposure_file": exp_file_name, "trait": trait_label,
                "outcome_file": outcome_file_name, "outcome_trait": outcome_trait,
                "status": mr_out["status"], "error": mr_out["error"],
                "harmonised_snps": len(mr_out["harmonised"]),
            })

    clump_summary_df = pd.DataFrame(clump_records)
    mr_run_summary_df = pd.DataFrame(mr_run_records)
    combined_results_df = pd.concat(all_mr_results, ignore_index=True) if all_mr_results else pd.DataFrame()

    clump_summary_df.to_csv(set_dir / "clumping_summary.csv", index=False)
    mr_run_summary_df.to_csv(set_dir / "mr_run_summary.csv", index=False)
    combined_results_df.to_csv(set_dir / "combined_mr_results.csv", index=False)

    print("\nClumping summary:")
    print(clump_summary_df)
    print("\nMR run summary:")
    print(mr_run_summary_df)
    print("\nOutputs saved under:", set_dir)

    _report(1.0, "Complete")

    return {
        "analysis_set_name": analysis_set_name,
        "clump_summary": clump_summary_df,
        "mr_run_summary": mr_run_summary_df,
        "combined_results": combined_results_df,
        "output_dir": str(set_dir),
    }

def run_pipeline_for_all_analysis_sets(skip_existing: bool = True, **kwargs) -> pd.DataFrame:
    """Loop run_pipeline_for_analysis_set() over every row in analysis_set_record.csv."""
    sets_df = load_analysis_set_record()
    overview = []

    for _, row in sets_df.iterrows():
        name = row["analysis_set_name"]
        out_dir = set_output_dir(name)

        if skip_existing and (out_dir / "combined_mr_results.csv").exists():
            print(f"Skipping '{name}' (results already exist).")
            overview.append({"analysis_set_name": name, "status": "skipped_existing"})
            continue

        try:
            run_pipeline_for_analysis_set(name, **kwargs)
            overview.append({"analysis_set_name": name, "status": "done"})
        except Exception as e:
            print(f"Failed for '{name}': {e}")
            overview.append({"analysis_set_name": name, "status": "failed", "error": str(e)})

    return pd.DataFrame(overview)