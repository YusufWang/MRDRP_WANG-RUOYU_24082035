"""
gwas_catalog_ftp.py

Automates what P1 did by hand: given a study accession, locate and download
its harmonised (GRCh38) summary statistics file from EBI's GWAS Catalog FTP
archive, then filter it down to genome-wide-significant variants.

Why this module exists (P2, 2026-07-23)
-----------------------------------------
The Summary Statistics REST API (gwas_catalog_client.py) turned out to have
two serious limits for this project's actual target traits (IGF1, SHBG,
ADIPOQ, GDF15, endometrial cancer): essentially none of the candidate
studies found for these traits were loaded into it, AND the endpoint used to
even check availability was observed rate-limited to as low as 10 requests/
hour. Both problems are specific to that REST API -- the plain FTP archive
it is a thin wrapper around has much broader coverage (85,000+ full
genome-wide datasets per EBI's own count) and is just file serving, not a
throttled REST API.

How it works
------------
EBI organises the FTP archive as:
    /pub/databases/gwas/summary_statistics/{range_folder}/{accession}/harmonised/{file}
where range_folder groups accessions into contiguous blocks of 1000, using
the SAME digit-width as the accession's own numeric part, e.g.:
    GCST000028   -> GCST000001-GCST001000/GCST000028/harmonised/
    GCST004988   -> GCST004001-GCST005000/GCST004988/harmonised/
    GCST90018866 -> GCST90018001-GCST90019000/GCST90018866/harmonised/
(all three confirmed against real, working EBI URLs on 2026-07-23). The
harmonised/ directory is browsable over plain HTTP (an Apache/nginx-style
"Index of ..." listing), so rather than guess the exact filename (which
encodes the PubMed ID and an EFO id, e.g.
"17463246-GCST000028-EFO_0001360.h.tsv.gz" -- not derivable from the
accession alone), this module reads that directory listing and downloads
whatever ".h.tsv.gz" file(s) it finds there.

-----------------------------------------------------------------------------
IMPORTANT -- please read before relying on this for real analysis
-----------------------------------------------------------------------------
The range-folder formula above is verified against three real, independently
confirmed EBI URLs. The directory-listing HTML parser, however, was written
against the *standard* Apache/nginx autoindex format and has NOT been
exercised against a real response (the sandbox that wrote this cannot reach
ftp.ebi.ac.uk). If list_harmonised_files() ever returns an empty list for a
study you're confident has harmonised data, call it with debug=True -- it
will print the raw HTML it received so we can see whether EBI's actual
markup differs from the standard format assumed here.
"""

from __future__ import annotations

import gzip
import re
import shutil
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd
import numpy as np
import requests
from scipy.stats import norm

FTP_HTTP_BASE = "https://ftp.ebi.ac.uk/pub/databases/gwas/summary_statistics"
REQUEST_TIMEOUT_SECONDS = 30
DOWNLOAD_CHUNK_BYTES = 1024 * 1024  # 1 MB

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "MRDRP-dashboard/0.1 (WQF7023 P2 project, Universiti Malaya)",
})


class GwasFtpError(Exception):
    """Raised when the FTP archive can't be located or read for a study."""


# =============================================================================
# URL construction
# =============================================================================

def compute_range_folder(accession: str) -> str:
    """
    e.g. 'GCST90083018' -> 'GCST90083001-GCST90084000'
    Verified 2026-07-23 against three real EBI URLs spanning old (6-digit)
    and new (8-digit) accession numbering.
    """
    if not accession.startswith("GCST"):
        raise ValueError(f"Not a GWAS Catalog accession: {accession!r}")
    numeric_str = accession[4:]
    if not numeric_str.isdigit():
        raise ValueError(f"Could not parse numeric part of accession: {accession!r}")
    digit_width = len(numeric_str)
    n = int(numeric_str)
    range_start = ((n - 1) // 1000) * 1000 + 1
    range_end = range_start + 999
    return f"GCST{range_start:0{digit_width}d}-GCST{range_end:0{digit_width}d}"


def harmonised_dir_url(accession: str) -> str:
    return f"{FTP_HTTP_BASE}/{compute_range_folder(accession)}/{accession}/harmonised/"


def raw_dir_url(accession: str) -> str:
    """The author-submitted (non-harmonised, build not guaranteed) directory."""
    return f"{FTP_HTTP_BASE}/{compute_range_folder(accession)}/{accession}/"


# =============================================================================
# Directory listing
# =============================================================================

def _parse_autoindex_links(html: str) -> List[str]:
    """
    Extract filenames from a standard Apache/nginx "Index of ..." directory
    listing. Confirmed 2026-07-24 against real EBI responses: the "Parent
    Directory" link is a site-root-relative absolute path (e.g.
    "/pub/databases/gwas/summary_statistics/.../"), not "../" -- so that
    form is excluded too, alongside query-string sort links and external URLs.
    """
    hrefs = re.findall(r'href="([^"]+)"', html, flags=re.IGNORECASE)
    names = []
    for href in hrefs:
        if href in ("../", "./"):
            continue
        if href.startswith("?"):  # column-sort links
            continue
        if href.startswith("http://") or href.startswith("https://"):
            continue
        if href.startswith("/"):  # site-root-relative parent-directory link
            continue
        names.append(href)
    return names


def _parse_autoindex_entries(html: str) -> dict:
    """
    Like _parse_autoindex_links(), but also captures the size column when
    present (e.g. "399M", "1.2K", "233M") -- returns {filename: size_str}.
    The <table>-based row format (confirmed 2026-07-24/25 against real EBI
    directory listings) is what carries size info here; a <pre>-based
    listing (no <tr> rows) still returns every filename via the same
    name-extraction logic as _parse_autoindex_links(), just with size=None
    for all of them, rather than silently returning nothing.
    """
    names = _parse_autoindex_links(html)
    sizes = {name: None for name in names}

    rows = re.findall(r"<tr>.*?</tr>", html, flags=re.DOTALL | re.IGNORECASE)
    for row in rows:
        href_match = re.search(r'href="([^"]+)"', row, flags=re.IGNORECASE)
        if not href_match:
            continue
        name = href_match.group(1)
        if name not in sizes:
            continue  # not a real entry per _parse_autoindex_links (e.g. parent-dir link)
        size_tokens = re.findall(r">\s*([\d.]+[KMGT]?|-)\s*</td>", row, flags=re.IGNORECASE)
        # last matching token in the row is the size column (date column
        # doesn't match this pattern); "-" means a directory (no size)
        sizes[name] = size_tokens[-1] if size_tokens and size_tokens[-1] != "-" else None
    return sizes


def list_directory_files(dir_url: str, debug: bool = False) -> List[str]:
    """List filenames in an FTP-over-HTTP directory. Returns [] if the
    directory doesn't exist (404) or listing is disabled."""
    try:
        resp = _SESSION.get(dir_url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise GwasFtpError(f"Network error listing {dir_url}: {e}") from e

    if debug:
        print(f"[gwas_catalog_ftp debug] GET {dir_url} -> {resp.status_code}")
        if resp.status_code != 404:
            print(resp.text[:3000])

    if resp.status_code == 404:
        return []
    if not resp.ok:
        raise GwasFtpError(f"Unexpected status {resp.status_code} listing {dir_url}")

    return _parse_autoindex_links(resp.text)


def list_directory_file_sizes(dir_url: str, debug: bool = False) -> dict:
    """Like list_directory_files(), but returns {filename: size_str_or_None}."""
    try:
        resp = _SESSION.get(dir_url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise GwasFtpError(f"Network error listing {dir_url}: {e}") from e

    if resp.status_code == 404:
        return {}
    if not resp.ok:
        raise GwasFtpError(f"Unexpected status {resp.status_code} listing {dir_url}")

    return _parse_autoindex_entries(resp.text)


def list_harmonised_files(accession: str, debug: bool = False) -> List[str]:
    """
    Filenames (not full URLs) of harmonised (".h.tsv.gz") files available
    for this study, or [] if the study has no harmonised directory / no such
    files in it.
    """
    files = list_directory_files(harmonised_dir_url(accession), debug=debug)
    return [f for f in files if f.endswith(".h.tsv.gz") or f.endswith(".h.tsv")]


def get_harmonised_file_url(accession: str, debug: bool = False) -> Optional[str]:
    """Full URL of the first harmonised file found for this study, or None."""
    files = list_harmonised_files(accession, debug=debug)
    if not files:
        return None
    return harmonised_dir_url(accession) + files[0]


def list_raw_files(accession: str, debug: bool = False) -> List[str]:
    """
    Filenames in the study's top-level (non-harmonised) FTP directory --
    the author-submitted file(s), for studies that don't have a harmonised/
    subfolder at all (this appears to include at least some gene-based
    burden test studies, confirmed 2026-07-23 for GCST90083018). Build is
    NOT guaranteed for these -- same caveat as a raw file in the P1 manual
    workflow. Excludes the "harmonised" subdirectory entry itself.
    """
    files = list_directory_files(raw_dir_url(accession), debug=debug)
    return [f for f in files if f != "harmonised/" and not f.endswith("/")]


def parse_size_str_to_bytes(size_str: Optional[str]) -> Optional[int]:
    """'233M' -> 244318208, '1.2G' -> ~1288490188, '793' (bytes, no suffix) -> 793. None/unparseable -> None."""
    if not size_str:
        return None
    match = re.match(r"^([\d.]+)\s*([KMGT])?$", size_str.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "").upper()
    multiplier = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[unit]
    return int(value * multiplier)


def build_from_filename(file_name: str) -> str:
    """Mirrors app.py's get_build_from_filename() for consistency."""
    lower = file_name.lower()
    if "grch37" in lower:
        return "GRCh37"
    if "grch38" in lower:
        return "GRCh38"
    return "Unknown"


def build_from_meta_yaml(dir_url: str, data_filename: str, debug: bool = False) -> Optional[str]:
    """
    GWAS-SSF files are typically accompanied by a "{filename}-meta.yaml"
    sidecar in the same directory. Rather than parse it as structured YAML
    (risks guessing the wrong field name for something not fully verified
    live), this does a simple, schema-agnostic substring scan of the raw
    text for a build mention -- robust to whatever the exact field name
    turns out to be. Returns "GRCh37"/"GRCh38" if found, else None (meta
    file missing, or it doesn't mention a build).
    """
    meta_url = dir_url + data_filename + "-meta.yaml"
    try:
        resp = _SESSION.get(meta_url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException:
        return None

    if debug:
        print(f"[gwas_catalog_ftp debug] GET {meta_url} -> {resp.status_code}")
        if resp.ok:
            print(resp.text[:2000])

    if not resp.ok:
        return None

    text_lower = resp.text.lower()
    if "grch38" in text_lower:
        return "GRCh38"
    if "grch37" in text_lower or "hg19" in text_lower:
        return "GRCh37"
    return None


def find_best_available_file(accession: str, debug: bool = False) -> Optional[dict]:
    """
    Pick the best file to use for `accession`, checking in this order
    (confirmed 2026-07-24 against real P1 accessions -- all 4 had a
    build-tagged file in the top-level raw directory, matching exactly what
    P1 downloaded by hand; only 3 of the 4 additionally had a harmonised/
    subfolder):

      1. A build-tagged file (name contains "buildGRCh37"/"buildGRCh38") in
         the top-level raw directory -- build known directly from the
         filename, no need to touch the harmonised/ pipeline at all. This is
         what P1 used, so preferring it keeps this path consistent with the
         existing project methodology.
      2. A harmonised/ file (".h.tsv.gz") -- build is GRCh38 by definition
         of EBI's harmonisation pipeline, but the *rows* still need to be
         checked individually (some may have failed harmonisation -- see
         filter_significant_from_local_file).
      3. Any other file in the top-level raw directory. Its "-meta.yaml"
         sidecar is checked for a build mention (GWAS-SSF studies usually
         ship one); if that doesn't resolve it either, build is "Unknown"
         and fetch_significant_from_ftp() will offer to liftover assuming
         GRCh37 (see liftover_grch37_to_grch38()).

    Note on file size (observed 2026-07-25): build-tagged raw files tend to
    be small (a few MB -- these look like pre-filtered/reduced files), while
    harmonised/ and plain raw files can be hundreds of MB to a few GB (full,
    unfiltered genome-wide data). Larger downloads take proportionally
    longer and are more exposed to any network hiccup, which is part of why
    fetch_significant_from_ftp() downloads to local disk rather than
    directly onto the Drive mount -- see that function's docstring.

    Returns None if no usable file at all is found. Otherwise returns:
        {"url": str, "filename": str, "size_str": str | None,
         "source": "raw_build_tagged" | "harmonised_pipeline" | "raw_unknown_build",
         "build": "GRCh38" | "GRCh37" | "Unknown",
         "build_source": "filename" | "harmonised_pipeline" | "meta_yaml" | None}
    """
    raw_entries = list_directory_file_sizes(raw_dir_url(accession), debug=debug)
    raw_files = [f for f in raw_entries if f != "harmonised/" and not f.endswith("/")]

    build_tagged = [f for f in raw_files if f.endswith(".tsv.gz") and build_from_filename(f) != "Unknown"]
    if build_tagged:
        filename = build_tagged[0]
        return {
            "url": raw_dir_url(accession) + filename,
            "filename": filename,
            "size_str": raw_entries.get(filename),
            "source": "raw_build_tagged",
            "build": build_from_filename(filename),
            "build_source": "filename",
        }

    harmonised_entries = list_directory_file_sizes(harmonised_dir_url(accession), debug=debug)
    harmonised_files = [f for f in harmonised_entries if f.endswith(".h.tsv.gz") or f.endswith(".h.tsv")]
    if harmonised_files:
        filename = harmonised_files[0]
        return {
            "url": harmonised_dir_url(accession) + filename,
            "filename": filename,
            "size_str": harmonised_entries.get(filename),
            "source": "harmonised_pipeline",
            "build": "GRCh38",
            "build_source": "harmonised_pipeline",
        }

    data_files = [f for f in raw_files if f.endswith(".tsv.gz")]
    if data_files:
        filename = data_files[0]
        meta_build = build_from_meta_yaml(raw_dir_url(accession), filename, debug=debug)
        return {
            "url": raw_dir_url(accession) + filename,
            "filename": filename,
            "size_str": raw_entries.get(filename),
            "source": "raw_unknown_build",
            "build": meta_build or "Unknown",
            "build_source": "meta_yaml" if meta_build else None,
        }

    return None


# =============================================================================
# Liftover (GRCh37 -> GRCh38) for files with no other build signal
# =============================================================================

def _normalize_chrom_for_liftover(chrom) -> Optional[str]:
    """UCSC chain files expect 'chr1'..'chr22','chrX','chrY','chrM' naming."""
    if chrom is None or (isinstance(chrom, float) and pd.isna(chrom)):
        return None
    s = str(chrom).strip()
    if s == "" or s.lower() == "nan":
        return None
    if s.upper() in ("MT", "M"):
        return "chrM"
    if s.lower().startswith("chr"):
        return s
    return f"chr{s}"


def liftover_grch37_to_grch38(
    df: pd.DataFrame,
    chrom_col: str,
    pos_col: str,
    debug: bool = False,
) -> pd.DataFrame:
    """
    Lift `chrom_col`/`pos_col` from GRCh37 to GRCh38 in place (returns a
    copy), using pyliftover -- a pure-Python implementation of UCSC's
    liftOver tool. The GRCh37<->hg19 coordinate systems are the same thing
    under two different names, as are GRCh38<->hg38, so LiftOver('hg19',
    'hg38') is the correct chain for GRCh37 -> GRCh38.

    The first call downloads and caches the (~a few MB) chain file from UCSC
    automatically -- no manual chain file management needed.

    This is designed to run AFTER p-value filtering, on a small number of
    rows (a few hundred to a few thousand significant variants) -- it does
    point-by-point conversion, which does not scale to whole-genome files
    but is fast enough at this size.

    Adds a "liftover_success" column. Rows where the chromosome name wasn't
    recognised, the locus has no mapping in GRCh38, or the mapping is
    ambiguous (multiple targets) get liftover_success=False and NaN
    chrom_col/pos_col -- these should be dropped by the caller if a clean,
    fully-GRCh38 result is wanted.
    """
    try:
        from pyliftover import LiftOver
    except ImportError as e:
        raise GwasFtpError(
            "pyliftover is not installed. Run: pip install pyliftover --break-system-packages"
        ) from e

    lo = LiftOver("hg19", "hg38")

    new_chrom: List[Optional[str]] = []
    new_pos: List[Optional[int]] = []
    success: List[bool] = []

    for _, row in df.iterrows():
        ucsc_chrom = _normalize_chrom_for_liftover(row[chrom_col])
        raw_pos = row[pos_col]

        if ucsc_chrom is None or pd.isna(raw_pos):
            new_chrom.append(None)
            new_pos.append(None)
            success.append(False)
            continue

        try:
            pos_0based = int(float(raw_pos)) - 1  # pyliftover uses 0-based coordinates
        except (TypeError, ValueError):
            new_chrom.append(None)
            new_pos.append(None)
            success.append(False)
            continue

        result = lo.convert_coordinate(ucsc_chrom, pos_0based)

        if not result:  # None (unrecognised chrom) or [] (deleted in target build)
            new_chrom.append(None)
            new_pos.append(None)
            success.append(False)
            continue

        target_chrom, target_pos_0based, _strand, _score = result[0]
        new_chrom.append(str(target_chrom).replace("chr", ""))
        new_pos.append(target_pos_0based + 1)  # back to 1-based
        success.append(True)

    out = df.copy()
    out[chrom_col] = new_chrom
    out[pos_col] = new_pos
    out["liftover_success"] = success

    if debug:
        n_ok = sum(success)
        print(f"[gwas_catalog_ftp debug] liftover: {n_ok} / {len(df)} rows mapped successfully")

    return out


# =============================================================================
# Download + filter
# =============================================================================

def download_file(url: str, dest_path: Path, progress_every_mb: int = 50, progress_callback=None) -> Path:
    """
    Stream a (possibly large) file to disk, printing progress periodically.
    If progress_callback is given, it's called as
    progress_callback(downloaded_bytes, total_bytes_or_None) after every
    chunk -- total_bytes is None if the server didn't send a Content-Length
    header. Added 2026-08-14 so the dashboard's FTP download button can
    drive a real st.progress() bar instead of just showing a spinner with
    no numeric feedback for however many minutes a large file takes.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _SESSION.get(url, stream=True, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            if not resp.ok:
                raise GwasFtpError(f"Download failed ({resp.status_code}) for {url}")
            total_bytes = None
            content_length = resp.headers.get("Content-Length")
            if content_length is not None:
                try:
                    total_bytes = int(content_length)
                except ValueError:
                    total_bytes = None
            downloaded = 0
            next_report = progress_every_mb * 1024 * 1024
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback is not None:
                        progress_callback(downloaded, total_bytes)
                    if downloaded >= next_report:
                        print(f"  ... downloaded {downloaded / (1024*1024):.0f} MB")
                        next_report += progress_every_mb * 1024 * 1024
    except requests.RequestException as e:
        raise GwasFtpError(f"Network error downloading {url}: {e}") from e

    # Defensive check: if dest_path sits on a network-synced mount (e.g. a
    # Google Drive mount in Colab), writes can occasionally appear to
    # succeed but not be immediately visible to a fresh open() -- fail
    # clearly here rather than raising a confusing FileNotFoundError deeper
    # inside pandas later. (Prefer a local, non-Drive work_dir to avoid this
    # class of issue entirely -- see fetch_significant_from_ftp's docstring.)
    if not dest_path.exists() or dest_path.stat().st_size == 0:
        raise GwasFtpError(
            f"Download appears to have failed silently: {dest_path} is missing or empty "
            f"after writing {downloaded:,} bytes. If dest_path is on a Google Drive mount, "
            "this is a known sync-latency issue -- use a local path (e.g. under /content/) "
            "for work_dir instead."
        )
    return dest_path


def _find_column(columns: List[str], candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in columns:
            return c
    return None


def filter_significant_from_local_file(
    local_path: Path,
    p_upper: float = 5e-8,
    chunksize: int = 200_000,
    source_build_hint: Optional[str] = None,
) -> pd.DataFrame:
    """
    Stream-read a (possibly multi-GB) .tsv.gz file in chunks, keeping only
    rows with p_value < p_upper, so the whole file never has to fit in
    memory at once.

    Build labelling, in priority order:
      1. If hm_chrom/hm_pos/hm_effect_allele/hm_other_allele columns are
         present, a row is "harmonised" (build=GRCh38) if all four are
         non-null for that row -- most granular, per-row truth, matching
         the dual raw+harmonised column layout some files/API modes use.
      2. Otherwise, if `source_build_hint` was given ("GRCh37" or "GRCh38",
         from either a "_buildGRCh38"-style raw filename, or simply from
         having been downloaded from the harmonised/ subfolder), a row gets
         that build if its plain (unprefixed) chromosome/position/allele
         columns are non-null. This covers real harmonised/ files that
         carry NO separate hm_-prefixed columns at all -- confirmed
         2026-07-25 against GCST90474405.h.tsv.gz, whose columns are
         chromosome/base_pair_location/effect_allele/other_allele/rsid/
         ID/hm_coordinate_conversion/hm_code with no hm_chrom/hm_pos -- the
         plain columns there already ARE the harmonised values, since the
         whole file is the harmonised product of that subfolder.
      3. Otherwise build is "Unknown" for every row.
    """
    kept_chunks = []
    rows_scanned = 0
    rows_kept = 0

    reader = pd.read_csv(local_path, sep="	", compression="infer", chunksize=chunksize, low_memory=False)

    p_col = None
    beta_col = None
    or_col = None
    se_col = None
    p_is_derived = False
    columns_resolved = False

    for chunk_idx, chunk in enumerate(reader):
        if not columns_resolved:
            columns_resolved = True
            p_col = _find_column(chunk.columns.tolist(), ["p_value", "P", "p", "pval"])
            if p_col is None:
                beta_col = _find_column(chunk.columns.tolist(), ["beta", "BETA", "effect", "estimate", "log_odds", "lnOR"])
                or_col = _find_column(chunk.columns.tolist(), ["odds_ratio", "OR", "or", "odds ratio", "oddsRatio"])
                se_col = _find_column(chunk.columns.tolist(), ["standard_error", "SE", "se"])
                if (beta_col or or_col) and se_col:
                    p_is_derived = True
                    print(
                        f"No p-value column found in {local_path.name}, but found "
                        f"{'beta' if beta_col else 'odds_ratio'} + standard_error -- deriving "
                        "p-value on the fly (p = 2*(1-Phi(|effect/SE|))) to filter on."
                    )
                else:
                    raise GwasFtpError(
                        f"Could not find a p-value column in {local_path.name}, and no "
                        "beta/odds_ratio + standard_error combination to derive one from either. "
                        f"Columns present: {chunk.columns.tolist()}"
                    )

        if p_is_derived:
            if beta_col:
                effect = pd.to_numeric(chunk[beta_col], errors="coerce")
            else:
                effect = np.log(pd.to_numeric(chunk[or_col], errors="coerce"))
            se = pd.to_numeric(chunk[se_col], errors="coerce")
            with np.errstate(divide="ignore", invalid="ignore"):
                z = effect / se
            computed_p = 2 * (1 - norm.cdf(z.abs()))
            sig_chunk = chunk[computed_p < p_upper]
        else:
            sig_chunk = chunk[pd.to_numeric(chunk[p_col], errors="coerce") < p_upper]
        rows_scanned += len(chunk)
        rows_kept += len(sig_chunk)
        if len(sig_chunk) > 0:
            kept_chunks.append(sig_chunk)

        # Large un-harmonised files can have tens of millions of rows and
        # take several minutes with no other output -- print progress every
        # ~10 chunks so this doesn't look stuck.
        if (chunk_idx + 1) % 10 == 0:
            print(f"  ... scanned {rows_scanned:,} rows, {rows_kept:,} significant so far")

    if not kept_chunks:
        return pd.DataFrame()

    df = pd.concat(kept_chunks, ignore_index=True)
    columns = df.columns.tolist()

    hm_chrom = _find_column(columns, ["hm_chrom"])
    hm_pos = _find_column(columns, ["hm_pos"])
    hm_effect = _find_column(columns, ["hm_effect_allele"])
    hm_other = _find_column(columns, ["hm_other_allele"])

    if hm_chrom and hm_pos and hm_effect and hm_other:
        df["harmonised"] = df[[hm_chrom, hm_pos, hm_effect, hm_other]].notna().all(axis=1)
        df["build"] = df["harmonised"].map({True: "GRCh38", False: "Unknown"})
    elif source_build_hint in ("GRCh37", "GRCh38"):
        core_cols = [c for c in [
            _find_column(columns, ["chromosome", "chrom", "CHR", "chr"]),
            _find_column(columns, ["base_pair_location", "position", "POS", "pos"]),
            _find_column(columns, ["effect_allele", "EA", "A1"]),
            _find_column(columns, ["other_allele", "OA", "A2"]),
        ] if c]
        has_geometry = df[core_cols].notna().all(axis=1) if core_cols else pd.Series(True, index=df.index)
        df["build"] = has_geometry.map({True: source_build_hint, False: "Unknown"})
        df["harmonised"] = df["build"] == "GRCh38"
    else:
        df["harmonised"] = False
        df["build"] = "Unknown"

    return df


def fetch_significant_from_ftp(
    accession: str,
    p_upper: float = 5e-8,
    work_dir: Optional[Path] = None,
    keep_downloaded_file: bool = False,
    attempt_liftover: bool = True,
    debug: bool = False,
    progress_callback=None,
) -> pd.DataFrame:
    """
    End-to-end: pick the best available file for `accession` on the FTP
    archive (see find_best_available_file() for the selection order),
    download it, filter to p < p_upper, and return the result. This is the
    FTP-based counterpart to
    gwas_catalog_client.fetch_significant_associations() -- use this one
    when the Summary Statistics API doesn't have the study (which is common
    for this project's target traits; see module docstring).

    Downloads to `work_dir` (default: a temp folder under the current
    directory) and deletes the full downloaded file afterwards unless
    keep_downloaded_file=True -- these files can be very large (hundreds of
    MB to a few GB), so the default keeps only the filtered result.

    IMPORTANT: pass a *local* work_dir (e.g. under /content/ in Colab), not
    a path inside a Google Drive mount. Confirmed 2026-07-24: writing a
    large file to a Drive-mounted path can appear to succeed and then still
    raise FileNotFoundError moments later when re-opened for reading, due
    to Drive's sync latency -- a local disk has no such issue.

    If the chosen file's build isn't confirmed GRCh38 -- filename says
    GRCh37, or nothing confirms the build at all (best["build"] == "Unknown",
    the common case for older/un-tagged submissions, where GRCh37 is by far
    the most likely actual build) -- and attempt_liftover=True (default),
    this runs liftover_grch37_to_grch38() on the (already p-value-filtered,
    so small) result. Adds a "liftover_attempted" column and updates
    "build"/"harmonised" for rows that succeeded. Set attempt_liftover=False
    to skip this and keep the original coordinates with build left as-is.
    """
    best = find_best_available_file(accession, debug=debug)
    if best is None:
        raise GwasFtpError(
            f"No usable file found for {accession} in either "
            f"{raw_dir_url(accession)} or its harmonised/ subfolder. "
            "Rerun with debug=True to see the raw directory listing response(s)."
        )

    file_url = best["url"]
    work_dir = work_dir or Path("./_gwas_ftp_downloads")
    local_path = work_dir / best["filename"]

    print(f"Using {best['source']} file (build: {best['build']}): {best['filename']}")
    print(f"Downloading {file_url}")
    print(f"  -> {local_path}")
    t0 = time.time()
    download_file(file_url, local_path, progress_callback=progress_callback)
    print(f"Downloaded in {time.time() - t0:.1f}s, filtering for p < {p_upper:.1e} ...")

    t1 = time.time()
    try:
        result = filter_significant_from_local_file(
            local_path, p_upper=p_upper,
            source_build_hint=best["build"] if best["build"] in ("GRCh37", "GRCh38") else None,
        )
    finally:
        if not keep_downloaded_file:
            try:
                local_path.unlink(missing_ok=True)
            except OSError:
                pass

    print(f"Filtered in {time.time() - t1:.1f}s. Found {len(result)} significant variant(s).")

    # Gate on the actual row-level result, not the directory-level "best"
    # assumption -- these can disagree (e.g. a harmonised/ file whose rows
    # didn't carry the expected columns), and the row-level truth is what
    # actually matters for deciding whether liftover is worth attempting.
    needs_liftover = len(result) > 0 and (
        "harmonised" not in result.columns or not result["harmonised"].all()
    )
    result["liftover_attempted"] = False

    if attempt_liftover and needs_liftover:
        chrom_col = _find_column(result.columns.tolist(), ["chromosome", "chrom", "CHR", "chr"])
        pos_col = _find_column(result.columns.tolist(), ["base_pair_location", "position", "POS", "pos"])
        if chrom_col and pos_col:
            print(f"Build not confirmed GRCh38 (assuming GRCh37) -- attempting liftover on {len(result)} row(s)...")
            rows_to_lift = ~result["harmonised"] if "harmonised" in result.columns else pd.Series(True, index=result.index)
            lifted = liftover_grch37_to_grch38(result[rows_to_lift], chrom_col, pos_col, debug=debug)
            lifted["liftover_attempted"] = True
            result = pd.concat([result[~rows_to_lift], lifted], ignore_index=True) if "harmonised" in result.columns else lifted
            result["build"] = result.apply(
                lambda r: "GRCh38" if r.get("liftover_success") else r.get("build", "Unknown"), axis=1
            )
            result["harmonised"] = result["build"] == "GRCh38"
            n_lifted_ok = int(result.get("liftover_success", pd.Series(dtype=bool)).sum())
            print(f"Liftover: {n_lifted_ok} / {len(lifted)} row(s) successfully mapped to GRCh38.")
        else:
            print("Skipped liftover: could not find both a chromosome and a position column.")

    return result