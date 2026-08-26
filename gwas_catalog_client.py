"""
gwas_catalog_client.py

Lightweight client for the NHGRI-EBI GWAS Catalog REST APIs, built for the
MRDRP dashboard (P2: GWAS Catalog Search page).

This module wraps TWO SEPARATE, INDEPENDENT EBI APIs. Understanding the split
is the whole point of this file:

1. Main GWAS Catalog REST API v2  (curated study/trait METADATA + free-text search)
   Base URL : https://www.ebi.ac.uk/gwas/rest/api/v2
   Docs     : https://www.ebi.ac.uk/gwas/rest/api/v2/docs
   Used for : typing a keyword ("endometrial cancer", "IGF1") -> finding EFO
              trait candidates -> finding which studies exist for that trait
              (accession, sample size, ancestry, whether full summary stats
              are available, PubMed id). This is the "search" layer.

2. Summary Statistics REST API  (actual variant-level association numbers)
   Base URL : https://www.ebi.ac.uk/gwas/summary-statistics/api
   Docs     : https://www.ebi.ac.uk/gwas/summary-statistics/docs/
   Used for : once a study accession is chosen, pulling real rows (rsID,
              chromosome, position, effect_allele, other_allele, beta or
              odds_ratio, se, effect_allele_frequency, p_value) filtered by
              p-value. This is the layer that feeds the MR pipeline -- you
              can ask directly for p_upper=5e-8 and get back only the
              genome-wide-significant variants, already carrying rsIDs, so
              there is no need to download the full flat file just to find
              the instrument SNPs.

-----------------------------------------------------------------------------
IMPORTANT -- please read before wiring this into the dashboard
-----------------------------------------------------------------------------
This module was written against EBI's published API documentation, but it
was NOT exercised against the live API from the sandbox that wrote it -- that
sandbox's outbound network access does not include ebi.ac.uk. Your Colab
environment DOES have normal internet access, so this is the first place to
actually run it.

Two things were done specifically because of that:

  1. Everywhere the exact response field name is uncertain (the whole Main
     API v2 side -- it's a newer API and EBI's own docs page for it doesn't
     publish a field-level schema), functions accept SEVERAL plausible
     spellings (snake_case and camelCase both appear across EBI's APIs) and
     fall back to keeping the raw dict under `_raw` rather than silently
     dropping data.
  2. Every public function takes a `debug: bool` argument. Pass debug=True to
     print the raw JSON of the first response, so you can see exactly what
     came back. If a column shows up empty and you can see it in the raw
     JSON, tell me the key name and I will wire it in.

Run this file directly (`python gwas_catalog_client.py`) once it is
somewhere with internet access, as a first smoke test. It exercises the
Summary Statistics side (which is fully documented with real examples, so
it is the part I'm confident about) and the Main API v2 side (best-effort).
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

# =============================================================================
# Config
# =============================================================================

MAIN_API_BASE = "https://www.ebi.ac.uk/gwas/rest/api/v2"
SUMSTATS_API_BASE = "https://www.ebi.ac.uk/gwas/summary-statistics/api"

# EBI asks API users to keep to roughly 15 requests/second on the main API.
# We are nowhere near that in an interactive dashboard, but paginated pulls
# (fetch_significant_associations) can fire many requests in a loop, so we
# add a small delay between pages as good citizenship.
REQUEST_DELAY_SECONDS = 0.15
REQUEST_TIMEOUT_SECONDS = 20

_SESSION = requests.Session()
_SESSION.headers.update({
    "Accept": "application/json",
    "User-Agent": "MRDRP-dashboard/0.1 (WQF7023 P2 project, Universiti Malaya)",
})


class GwasCatalogAPIError(Exception):
    """Raised when the API returns something we cannot recover from."""


class GwasCatalogRateLimitError(GwasCatalogAPIError):
    """
    Raised specifically when the API returns 429 Too Many Requests -- lets
    callers show a distinct "you're being rate-limited, wait and retry"
    message instead of a generic error. Confirmed 2026-08-13: app.py
    already expected this class (referencing
    gwas_catalog_client.GwasCatalogRateLimitError and its .retry_after
    attribute in two places on the GWAS Catalog Search page) but it was
    never actually defined here -- so instead of the intended rate-limit
    message, hitting a real 429 raised an unrelated AttributeError from
    the except clause itself trying to look up this missing class,
    masking the real problem. This wasn't noticed earlier because the
    Summary Statistics API's rate limit is very low (observed as low as
    10 requests/hour) and simply hadn't been hit until now.
    """
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


# =============================================================================
# Low-level HTTP helpers
# =============================================================================

def _get_json(url: str, params: Optional[dict] = None, debug: bool = False) -> Optional[dict]:
    """
    GET a URL, return parsed JSON, or None on 404.
    Raises GwasCatalogRateLimitError on 429, GwasCatalogAPIError on other
    non-2xx statuses or network errors.
    """
    try:
        resp = _SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise GwasCatalogAPIError(f"Network error calling {url}: {e}") from e

    if resp.status_code == 404:
        return None

    if resp.status_code == 429:
        retry_after_header = resp.headers.get("Retry-After")
        retry_after = None
        if retry_after_header is not None:
            try:
                retry_after = float(retry_after_header)
            except ValueError:
                retry_after = None
        raise GwasCatalogRateLimitError(
            f"GWAS Catalog API rate limit hit (429) for {resp.url}", retry_after=retry_after
        )

    if not resp.ok:
        body_preview = resp.text[:500]
        # An HTML error page (common for infrastructure-level failures, like a
        # web server itself returning 500, rather than the API returning a
        # structured error) is noise, not useful diagnostic content, in a
        # message meant to be read by a person -- confirmed 2026-08-13 when a
        # real 500 from EBI dumped a full raw HTML page into the dashboard.
        # Keep the failure fully visible (status code, URL, plain-English
        # reason) without the markup. A well-formed error body (JSON or plain
        # text) is still shown as before, since that IS useful.
        if body_preview.strip().lower().startswith(("<!doctype", "<html")):
            raise GwasCatalogAPIError(
                f"GWAS Catalog API returned {resp.status_code} for {resp.url} "
                "(the server returned an HTML error page rather than a JSON response -- "
                "this usually means a problem on EBI's end, not with the request itself)."
            )
        raise GwasCatalogAPIError(
            f"GWAS Catalog API returned {resp.status_code} for {resp.url}: {body_preview}"
        )

    try:
        data = resp.json()
    except ValueError as e:
        raise GwasCatalogAPIError(f"Non-JSON response from {resp.url}: {e}") from e

    if debug:
        print(f"[gwas_catalog_client debug] GET {resp.url} -> {resp.status_code}")
        print(data)

    return data


def _first_present(d: dict, candidates: List[str]) -> Any:
    """Return the value of the first key in `candidates` that exists in `d`."""
    for key in candidates:
        if key in d and d[key] not in (None, ""):
            return d[key]
    return None


def _extract_study_trait_names(item: dict) -> Optional[str]:
    """
    Confirmed 2026-07-23 against a live /v2/studies/{accession} response:
    trait info comes back as a LIST under "efo_traits", each entry shaped
    like {"efo_id": "EFO_0004996", "efo_trait": "type 1 diabetes
    nephropathy"} -- not a flat string field as originally guessed. If a
    study is mapped to more than one trait, names are joined with "; ".
    """
    efo_traits = item.get("efo_traits")
    if isinstance(efo_traits, list) and efo_traits:
        names = [t.get("efo_trait") for t in efo_traits if isinstance(t, dict) and t.get("efo_trait")]
        if names:
            return "; ".join(names)
    # Fall back to the old flat-field guesses, in case some study shapes
    # (or a future API version) don't use the efo_traits list.
    return _first_present(item, ["efo_trait", "efoTrait", "trait", "mapped_trait", "mappedTrait"])


def _extract_embedded_collection(payload: dict) -> List[dict]:
    """
    HAL-style APIs put lists of resources under `_embedded`. Different EBI
    APIs key that dict differently (e.g. "efoTraits" vs "efo-traits" vs
    "studies"), and the Summary Statistics API even encodes the list as a
    dict of string indices ({"0": {...}, "1": {...}}) instead of a JSON
    array. This function is deliberately agnostic to the key name and to
    which of those two shapes is used, so callers don't have to guess.
    """
    embedded = payload.get("_embedded")
    if embedded is None:
        # Some list endpoints may not use HAL at all -- fall back to common
        # top-level list keys just in case.
        for key in ("content", "results", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return []

    for value in embedded.values():
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            # dict-of-index form, e.g. {"0": {...}, "1": {...}}
            try:
                return [value[k] for k in sorted(value.keys(), key=lambda x: int(x))]
            except (ValueError, TypeError):
                return list(value.values())
    return []


def _next_link(payload: dict) -> Optional[str]:
    links = payload.get("_links", {})
    next_link = links.get("next")
    if isinstance(next_link, dict):
        return next_link.get("href")
    return None


def _looks_like_ontology_id(value: str) -> bool:
    """True for short-form ontology IDs like 'EFO_0006842' or 'MONDO_0004979'."""
    return bool(re.match(r"^[A-Za-z]+_[0-9]+$", value.strip()))


# =============================================================================
# Main GWAS Catalog REST API v2 -- trait / study search (metadata layer)
# =============================================================================

def search_efo_traits(keyword: str, size: int = 20, debug: bool = False) -> pd.DataFrame:
    """
    Free-text search for EFO traits, e.g. search_efo_traits("endometrial cancer").

    Per EBI's v2 docs, searching the efo-traits endpoint with a free-text
    term returns any trait whose name contains that term (so "COVID-19"
    can also surface "long COVID-19", "COVID-19 symptoms measurement", etc).
    Use the returned efo_id for precise downstream queries rather than the
    trait name string.

    Returns a DataFrame with (best-effort) columns:
        efo_id, trait_name, uri, _raw
    """
    url = f"{MAIN_API_BASE}/efo-traits"
    payload = _get_json(url, params={"efo_trait": keyword, "size": size}, debug=debug)
    if payload is None:
        return pd.DataFrame(columns=["efo_id", "trait_name", "uri"])

    rows = []
    for item in _extract_embedded_collection(payload):
        rows.append({
            "efo_id": _first_present(item, ["efo_id", "efoId", "short_form", "shortForm", "id"]),
            "trait_name": _first_present(item, ["trait", "efo_trait", "efoTrait", "trait_name", "name"]),
            "uri": _first_present(item, ["uri", "efo_uri", "efoUri"]),
            "_raw": item,
        })
    return pd.DataFrame(rows)


# =============================================================================
# Search fallback -- abbreviation/synonym matching (P2, added 2026-07-28)
# =============================================================================
# search_efo_traits() above does a literal substring match against EFO trait
# names, so common abbreviations ("IGF1", "GDF15", "BMI") often miss when the
# EFO trait's registered name is the fully spelled-out form ("insulin-like
# growth factor 1", "body mass index"). The functions below add three
# fallback strategies on top of the unchanged literal search, tried in order.

# Local abbreviation -> formal-term-candidates table. Deliberately small and
# hand-maintained rather than exhaustive -- add an entry whenever a real
# search misses, so the table grows to match what this project actually
# searches for. Keys are normalised the same way canonical_trait_name() in
# app.py normalises trait strings (uppercase, alphanumeric only), so lookups
# are case/punctuation-insensitive.
TRAIT_ALIAS_SYNONYMS: Dict[str, List[str]] = {
    "IGF1": ["insulin-like growth factor 1", "insulin like growth factor I"],
    "SHBG": ["sex hormone binding globulin", "sex hormone-binding globulin"],
    "ADIPOQ": ["adiponectin"],
    "GDF15": ["growth differentiation factor 15", "GDF-15"],
    "BMI": ["body mass index"],
    "T2D": ["type 2 diabetes", "type 2 diabetes mellitus"],
    "T1D": ["type 1 diabetes", "type 1 diabetes mellitus"],
    "CAD": ["coronary artery disease", "coronary heart disease"],
    "LDL": ["LDL cholesterol", "low density lipoprotein cholesterol"],
    "HDL": ["HDL cholesterol", "high density lipoprotein cholesterol"],
    "TC": ["total cholesterol"],
    "TG": ["triglycerides"],
    "SBP": ["systolic blood pressure"],
    "DBP": ["diastolic blood pressure"],
    "CRP": ["C-reactive protein"],
    "HBA1C": ["glycated haemoglobin", "hemoglobin A1c"],
    "EGFR": ["estimated glomerular filtration rate"],
    "WHR": ["waist-hip ratio", "waist to hip ratio"],
}


def _alias_expansions_for(keyword: str) -> List[str]:
    """Look up `keyword` in TRAIT_ALIAS_SYNONYMS, case/punctuation-insensitive."""
    key = re.sub(r"[^A-Z0-9]+", "", keyword.upper())
    return TRAIT_ALIAS_SYNONYMS.get(key, [])


OLS_API_BASE = "https://www.ebi.ac.uk/ols4/api"


def ols_search_efo_synonyms(keyword: str, rows: int = 10, debug: bool = False) -> List[Dict[str, Any]]:
    """
    Query EBI's Ontology Lookup Service (OLS4) for EFO terms matching
    `keyword`. Unlike the GWAS Catalog's own efo-traits endpoint (literal
    substring match on the trait name only), OLS indexes each term's
    registered synonyms, so a search for "IGF1" can surface the term whose
    official label is "insulin-like growth factor 1" via its synonym list.

    Returns a best-effort list of {"efo_id": ..., "label": ..., "synonyms": [...]}
    dicts, in OLS's own relevance order. This is a *candidate generator only*
    -- OLS covers all of EFO, not just traits the GWAS Catalog has actually
    indexed studies for, so callers should confirm each candidate against
    search_efo_traits()/search_studies() before trusting it (this is exactly
    what search_efo_traits_with_fallback() below does).

    NOTE: like the rest of this module's Main API v2 support, this was
    written against EBI's published OLS4 API documentation but not
    exercised against the live API from the sandbox that wrote it (no
    ebi.ac.uk network access there). Pass debug=True to see the raw
    response the first time this runs in Colab.
    """
    url = f"{OLS_API_BASE}/search"
    params = {"q": keyword, "ontology": "efo", "rows": rows}
    try:
        payload = _get_json(url, params=params, debug=debug)
    except GwasCatalogAPIError:
        return []
    if not payload:
        return []

    docs = payload.get("response", {}).get("docs", [])
    results = []
    for doc in docs:
        obo_id = doc.get("obo_id") or doc.get("short_form")
        if not obo_id:
            continue
        synonyms = doc.get("synonym") or []
        if isinstance(synonyms, str):
            synonyms = [synonyms]
        results.append({
            "efo_id": str(obo_id).replace(":", "_"),
            "label": doc.get("label"),
            "synonyms": synonyms,
        })
    return results


def search_efo_traits_with_fallback(keyword: str, size: int = 20, debug: bool = False) -> pd.DataFrame:
    """
    Wraps search_efo_traits() with three fallback strategies, tried in order,
    stopping as soon as one returns a non-empty result:

      1. Literal search_efo_traits(keyword) -- unchanged behaviour, tried first.
      2. Local alias table (TRAIT_ALIAS_SYNONYMS): if `keyword` matches a
         known abbreviation, retry with each registered formal expansion.
      3. EBI OLS synonym lookup (ols_search_efo_synonyms): each OLS hit's
         label and synonyms are tried as fresh search_efo_traits() queries
         in turn (not returned directly -- see that function's docstring).
      4. Loosened query: if `keyword` is multi-word, retry with just the
         first word.

    Every attempt is recorded, in order, in the returned DataFrame's
    `.attrs["search_log"]` as {"strategy", "query", "row_count"} dicts, so
    the caller can show *which* strategy actually worked rather than
    silently substituting a different search term.
    """
    search_log: List[Dict[str, Any]] = []

    def _try(strategy: str, query: str) -> Optional[pd.DataFrame]:
        try:
            result = search_efo_traits(query, size=size, debug=debug)
        except GwasCatalogAPIError as e:
            # Confirmed 2026-08-21: without this, a single 500/429 on the
            # FIRST strategy tried crashed the whole fallback chain --
            # the alias table, OLS4 synonym lookup, and loosened-query
            # strategies never got a chance to run at all. Treat an API
            # error the same way as "this attempt found nothing" so the
            # chain keeps going, but record it distinctly in search_log
            # so a caller can tell "genuinely no matches" apart from
            # "couldn't even ask".
            search_log.append({"strategy": strategy, "query": query, "row_count": 0, "error": str(e)})
            return None
        search_log.append({"strategy": strategy, "query": query, "row_count": len(result)})
        return result if len(result) > 0 else None

    result = _try("literal", keyword)
    if result is not None:
        result.attrs["search_log"] = search_log
        return result

    for alias_query in _alias_expansions_for(keyword):
        result = _try("alias_table", alias_query)
        if result is not None:
            result.attrs["search_log"] = search_log
            return result

    for ols_hit in ols_search_efo_synonyms(keyword, debug=debug):
        candidate_terms = [ols_hit.get("label")] + list(ols_hit.get("synonyms") or [])
        for term in candidate_terms:
            if not term or term.strip().lower() == keyword.strip().lower():
                continue
            result = _try("ols_synonym", term)
            if result is not None:
                result.attrs["search_log"] = search_log
                return result

    keyword_words = keyword.strip().split()
    if len(keyword_words) > 1:
        first_word = keyword_words[0]
        result = _try("loosened_first_word", first_word)
        if result is not None:
            result.attrs["search_log"] = search_log
            return result

    empty = pd.DataFrame(columns=["efo_id", "trait_name", "uri"])
    empty.attrs["search_log"] = search_log
    return empty


def search_studies(
    efo_trait: Optional[str] = None,
    efo_uri: Optional[str] = None,
    disease_trait: Optional[str] = None,
    accession_id: Optional[str] = None,
    pubmed_id: Optional[str] = None,
    size: int = 20,
    debug: bool = False,
) -> pd.DataFrame:
    """
    List studies matching the given filter(s). At least one filter should be
    given -- typically an efo_id (from search_efo_traits) or a free-text
    disease_trait.

    Field-1 was verified working against the live API on 2026-07-23 (trait
    free-text search) -- but querying *studies* by EFO id came back empty
    for every trait tried, which means the parameter name/format this
    function guessed was wrong. Rather than guess again and cost another
    round trip, this function now tries several plausible variants in turn
    and uses the first one that returns any rows:

        efo_trait=<id>              (e.g. EFO_0006842, as originally guessed)
        efo_id=<id>
        efo_trait=<id colon-form>   (e.g. EFO:0006842)
        efo_id=<id colon-form>
        efo_trait=<uri>             (if efo_uri was supplied, e.g. from the
                                      'uri' column search_efo_traits() returns)
        efo_uri=<uri>

    Pass debug=True to see the raw response of every variant tried (printed
    in order) -- that tells us definitively which one is correct, so this
    function's variant list can be trimmed down once confirmed.

    Returns a DataFrame with columns:
        accession, trait_name, disease_trait, pubmed_id, sample_size,
        has_summary_stats, snp_count, cohort, _raw
    trait_name and has_summary_stats were confirmed against a live response
    on 2026-07-23 (trait_name comes from the nested "efo_traits" list;
    has_summary_stats from "full_summary_stats_available"). Note that
    has_summary_stats reflects the MAIN catalog's own record of whether a
    full genome-wide dataset exists at all -- a study can have
    has_summary_stats=True here and still not (yet) be loaded into the
    separate Summary Statistics API that check_summary_stats_available()
    and fetch_significant_associations() use; a study with
    has_summary_stats=False will never pass that check, because the main
    catalog itself is saying no such dataset exists.
    plus an empty-frame `.attrs["variants_tried"]` list for troubleshooting
    when nothing matched.
    """
    if not any([efo_trait, efo_uri, disease_trait, accession_id, pubmed_id]):
        raise ValueError(
            "search_studies needs at least one of: efo_trait, efo_uri, disease_trait, accession_id, pubmed_id"
        )

    url = f"{MAIN_API_BASE}/studies"

    candidate_params: List[dict] = []

    if efo_trait:
        if _looks_like_ontology_id(efo_trait):
            colon_form = efo_trait.replace("_", ":", 1)
            candidate_params.extend([
                {"efo_trait": efo_trait},
                {"efo_id": efo_trait},
                {"efo_trait": colon_form},
                {"efo_id": colon_form},
            ])
        else:
            # looks like free-text rather than an ID -- just try it as-is
            candidate_params.append({"efo_trait": efo_trait})

    if efo_uri:
        candidate_params.append({"efo_trait": efo_uri})
        candidate_params.append({"efo_uri": efo_uri})

    if disease_trait:
        candidate_params.append({"disease_trait": disease_trait})
    if accession_id:
        candidate_params.append({"accession_id": accession_id})
    if pubmed_id:
        candidate_params.append({"pubmed_id": pubmed_id})

    variants_tried = []
    payload = None

    for params in candidate_params:
        full_params = {**params, "size": size}
        try:
            result = _get_json(url, params=full_params, debug=debug)
        except GwasCatalogAPIError as e:
            # Same rationale as search_efo_traits_with_fallback()'s _try():
            # one candidate parameter format hitting a 500/429 shouldn't
            # stop the other formats from being tried.
            variants_tried.append({"params": params, "row_count": 0, "error": str(e)})
            continue
        rows = _extract_embedded_collection(result) if result else []
        variants_tried.append({"params": params, "row_count": len(rows)})
        if rows:
            payload = result
            break

    if debug:
        print("[gwas_catalog_client debug] search_studies variants tried (in order):")
        for v in variants_tried:
            print(f"    {v['params']} -> {v['row_count']} row(s)")

    if payload is None:
        empty = pd.DataFrame(columns=["accession", "trait_name", "disease_trait", "sample_size", "has_summary_stats", "snp_count", "cohort"])
        empty.attrs["variants_tried"] = variants_tried
        return empty

    rows = []
    for item in _extract_embedded_collection(payload):
        accession = _first_present(item, ["accession_id", "accessionId", "study_accession", "studyAccession", "accession"])
        cohort = item.get("cohort")
        rows.append({
            "accession": accession,
            "trait_name": _extract_study_trait_names(item),
            "disease_trait": _first_present(item, ["disease_trait", "diseaseTrait", "reported_trait", "reportedTrait"]),
            "pubmed_id": _first_present(item, ["pubmed_id", "pubmedId"]),
            "sample_size": _first_present(item, ["initial_sample_size", "initialSampleSize", "sample_size", "sampleSize"]),
            # Confirmed 2026-07-23 against a live response: the real field is
            # "full_summary_stats_available" (boolean). The other spellings
            # are kept as a fallback only.
            "has_summary_stats": _first_present(item, ["full_summary_stats_available", "full_pvalue_set", "fullPvalueSet", "has_summary_statistics", "hasSummaryStatistics"]),
            "snp_count": _first_present(item, ["snp_count", "snpCount"]),
            "cohort": "; ".join(cohort) if isinstance(cohort, list) else cohort,
            "_raw": item,
        })

    df = pd.DataFrame(rows)
    df.attrs["variants_tried"] = variants_tried
    return df


def get_study_ancestries(accession_id: str, debug: bool = False) -> pd.DataFrame:
    """List ancestry/population groups recruited for a given study accession."""
    url = f"{MAIN_API_BASE}/studies/{accession_id}/ancestries"
    payload = _get_json(url, debug=debug)
    if payload is None:
        return pd.DataFrame()

    rows = []
    for item in _extract_embedded_collection(payload):
        rows.append({
            "ancestry": _first_present(item, ["broad_ancestral_category", "broadAncestralCategory", "ancestry"]),
            "number_of_individuals": _first_present(item, ["number_of_individuals", "numberOfIndividuals"]),
            "country_of_recruitment": _first_present(item, ["country_of_recruitment", "countryOfRecruitment"]),
            "_raw": item,
        })
    return pd.DataFrame(rows)


# =============================================================================
# Summary Statistics API -- actual variant-level data (this part is fully
# verified against EBI's published request/response examples)
# =============================================================================

def check_summary_stats_available(accession_id: str) -> bool:
    """
    True if `accession_id` is loaded into the separate Summary Statistics
    database (i.e. GET /summary-statistics/api/studies/{accession} resolves).
    This is the real gate for whether fetch_significant_associations() will
    work -- a study can look promising in the main catalog and still 404
    here, in which case fall back to the FTP flat-file route (same as P1).
    """
    url = f"{SUMSTATS_API_BASE}/studies/{accession_id}"
    payload = _get_json(url)
    return payload is not None


def fetch_significant_associations(
    accession_id: str,
    p_upper: float = 5e-8,
    size: int = 500,
    max_pages: int = 50,
    reveal: Optional[str] = None,
    debug: bool = False,
) -> pd.DataFrame:
    """
    Pull genome-wide-significant variants for a study directly from the
    Summary Statistics API, without downloading the full flat file.

    This is the key P2 building block for exposure instrument selection: it
    plays the same role that P1's "download full file -> filter by p-value
    locally" step played, except the filtering happens server-side and the
    rsIDs come back already resolved (variant_id in the response *is* the
    rsID -- no separate rsID-mapping step needed for API-sourced data).

    Columns returned are the API's native field names so they line up
    directly with the dashboard's existing `inspect_columns()` detection
    logic: variant_id, chromosome, base_pair_location, effect_allele,
    other_allele, beta, odds_ratio, se, effect_allele_frequency, p_value,
    plus study_accession / trait / code for traceability.

    Genomic build
    -------------
    reveal=None (the default here, and the API's own default) returns the
    study's HARMONISED values under these same plain field names -- EBI's
    docs state this explicitly: "Default data values displayed are the
    harmonised values." The GWAS Catalog's harmonisation pipeline always
    targets GRCh38, so under the default there is no separate "build" field
    to read -- these coordinates already ARE GRCh38, for every row where
    harmonisation succeeded. Per the same docs, a row where harmonisation
    could not be done comes back with null chromosome/base_pair_location/
    effect_allele/other_allele. This function turns that signal into two
    convenience columns:
        harmonised : bool  -- True if all four of those fields are present
        build      : "GRCh38" if harmonised else "Unknown"
    This plays the same role that the "_buildGRCh38" filename suffix played
    for the manually-downloaded files in P1 -- except it's read from the
    data itself rather than a filename, which did not exist for this
    endpoint's previous "raw" default (that was this function's bug).

    reveal="raw" returns only the original, author-submitted values -- build
    is NOT guaranteed here, exactly the same ambiguity as an un-suffixed raw
    file in the P1 FTP workflow. harmonised/build are not computed in this
    mode (both columns come back False / "Unknown" for every row) since raw
    values carry no such guarantee.
    reveal="all" returns the raw values under the plain names AND a second,
    hm_-prefixed copy of the harmonised fields alongside them. harmonised/
    build are computed from the hm_-prefixed columns in this mode.
    """
    url = f"{SUMSTATS_API_BASE}/studies/{accession_id}/associations"
    params = {"p_upper": p_upper, "size": size, "reveal": reveal}

    all_rows: List[dict] = []
    next_url = url
    next_params = params

    for page_idx in range(max_pages):
        payload = _get_json(next_url, params=next_params, debug=(debug and page_idx == 0))
        if payload is None:
            break

        page_rows = _extract_embedded_collection(payload)
        if not page_rows:
            break
        all_rows.extend(page_rows)

        next_href = _next_link(payload)
        if not next_href:
            break

        next_url = next_href
        next_params = None  # params are already encoded in the next href
        time.sleep(REQUEST_DELAY_SECONDS)

    if not all_rows:
        empty = pd.DataFrame(columns=[
            "variant_id", "chromosome", "base_pair_location", "effect_allele",
            "other_allele", "beta", "odds_ratio", "se",
            "effect_allele_frequency", "p_value", "study_accession", "trait",
            "harmonised", "build",
        ])
        return empty

    df = pd.DataFrame(all_rows)
    # Drop the per-row _links noise if present; keep everything else as-is.
    if "_links" in df.columns:
        df = df.drop(columns=["_links"])

    if reveal == "raw":
        df["harmonised"] = False
        df["build"] = "Unknown"
    else:
        # reveal is None (API default = harmonised) or "all" (hm_-prefixed
        # columns present alongside the raw ones).
        prefix = "hm_" if reveal == "all" else ""
        core_cols = [f"{prefix}chromosome", f"{prefix}base_pair_location",
                     f"{prefix}effect_allele", f"{prefix}other_allele"]
        present_core_cols = [c for c in core_cols if c in df.columns]
        if present_core_cols:
            df["harmonised"] = df[present_core_cols].notna().all(axis=1)
        else:
            df["harmonised"] = False
        df["build"] = df["harmonised"].map({True: "GRCh38", False: "Unknown"})

    return df


def fetch_variant_in_study(accession_id: str, rsid: str, reveal: Optional[str] = None, debug: bool = False) -> Optional[dict]:
    """
    Look up a single variant's association stats within one study -- the
    efficient way to pull outcome data for a short list of clumped
    instrument SNPs, instead of downloading the whole outcome flat file.
    Returns None if the variant/study combination is not found.

    reveal=None (default) returns the harmonised (GRCh38) values, matching
    fetch_significant_associations()'s default -- important so the outcome
    lookup lands on the same build as the exposure instrument selection.
    """
    url = f"{SUMSTATS_API_BASE}/associations/{rsid}"
    params = {"study_accession": accession_id, "reveal": reveal}
    payload = _get_json(url, params=params, debug=debug)
    if payload is None:
        return None
    rows = _extract_embedded_collection(payload)
    return rows[0] if rows else None


def fetch_variants_in_study(accession_id: str, rsids: List[str], reveal: Optional[str] = None) -> pd.DataFrame:
    """Batch version of fetch_variant_in_study for a list of instrument SNPs."""
    rows = []
    for rsid in rsids:
        row = fetch_variant_in_study(accession_id, rsid, reveal=reveal)
        if row is not None:
            rows.append(row)
        time.sleep(REQUEST_DELAY_SECONDS)
    df = pd.DataFrame(rows)
    if "_links" in df.columns:
        df = df.drop(columns=["_links"])
    return df


# ============================================================================
# Self-test
# ============================================================================

def self_test() -> None:
    """
    Quick smoke test. Run this first on a machine with real internet access
    (Colab, not the Claude sandbox this was authored in).
    """
    print("=== 1. Summary Statistics API: known study, small page ===")
    df = fetch_significant_associations("GCST005038", p_upper=1e-3, size=5, max_pages=1)
    print(df.head())
    if "harmonised" in df.columns and len(df) > 0:
        n_harmonised = int(df["harmonised"].sum())
        print(f"harmonised (GRCh38) rows: {n_harmonised} / {len(df)}")
    print()

    print("=== 2. Summary Statistics API: single variant lookup ===")
    row = fetch_variant_in_study("GCST005038", "rs10875231")
    print(row)
    print()

    print("=== 3. Main API v2: EFO trait free-text search (best-effort parsing) ===")
    traits = search_efo_traits("endometrial cancer", size=5, debug=True)
    print(traits)
    print()

    if len(traits) > 0 and traits.iloc[0]["efo_id"]:
        print("=== 4. Main API v2: studies for first trait hit (best-effort parsing, multi-variant retry) ===")
        first_trait = traits.iloc[0]
        studies = search_studies(efo_trait=first_trait['efo_id'], efo_uri=first_trait.get('uri'), size=5, debug=True)
        print(studies)


if __name__ == '__main__':
    self_test()
