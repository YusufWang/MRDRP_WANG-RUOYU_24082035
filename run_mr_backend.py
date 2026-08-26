import os
import sys
import getpass

PROJECT_ROOT = "/home/owner/wangruoyu_wqf7023_mrdrp/MRDRP-main"
sys.path.insert(0, PROJECT_ROOT)

# ---- Same rpy2 connection check as your Colab Cell 1.11 ----
import rpy2.robjects as robjects
from rpy2.robjects.packages import importr

r_version = robjects.r("R.version.string")[0]
print("R version from rpy2:")
print(r_version)

TwoSampleMR = importr("TwoSampleMR")
ieugwasr = importr("ieugwasr")
print("rpy2 can import TwoSampleMR and ieugwasr successfully.")

# ---- Same OpenGWAS JWT setup as your Colab Cell 15 ----
OPENGWAS_JWT = getpass.getpass("Paste your OpenGWAS JWT token here: ").strip()
if OPENGWAS_JWT.startswith("Bearer "):
    OPENGWAS_JWT = OPENGWAS_JWT.replace("Bearer ", "").strip()
if len(OPENGWAS_JWT) == 0:
    raise ValueError("OpenGWAS JWT token is empty.")
if not OPENGWAS_JWT.startswith("eyJ"):
    print("WARNING: This token does not start with 'eyJ'. Please check whether you copied the correct JWT token.")

os.environ["OPENGWAS_JWT"] = OPENGWAS_JWT
robjects.r.assign("opengwas_jwt_py", OPENGWAS_JWT)
robjects.r("Sys.setenv(OPENGWAS_JWT = opengwas_jwt_py)")
print("OpenGWAS JWT has been set in Python and R session.")
print("Token length:", len(OPENGWAS_JWT))

# ---- Same recognition check as your Colab Cell 16 ----
print("Token recognised by Python os.environ:", bool(os.environ.get("OPENGWAS_JWT")))

# ---- NEW: confirm ieugwasr itself (not just os.environ) sees the token ----
r_seen_token = robjects.r('ieugwasr::get_opengwas_jwt()')[0]
print("Token seen by ieugwasr::get_opengwas_jwt():", "present, length " + str(len(r_seen_token)) if r_seen_token else "EMPTY -- ieugwasr does not see it!")

# ---- Run the pipeline, then print FULL (untruncated) diagnostics ----
import pandas as pd
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

import mr_pipeline
import importlib
importlib.reload(mr_pipeline)

print("")
print("mr_pipeline.py loaded from:", mr_pipeline.__file__)
print("PROJECT_ROOT auto-detected as:", mr_pipeline.PROJECT_ROOT)

print("")
print("===== Running the pipeline for New_Analysis_Set_07 =====")
result = mr_pipeline.run_pipeline_for_analysis_set('New_Analysis_Set_07')

print("")
print("===== FULL clumping summary (all columns) =====")
print(result["clump_summary"].to_string())

print("")
print("===== FULL MR run summary (all columns) =====")
print(result["mr_run_summary"].to_string())

print("")
print(f"{len(result['combined_results'])} MR result row(s) produced.")

# ---- Diagnostic: raw content of the analysis_set_record.csv row for this set ----
print("")
print("===== Raw analysis_set_record.csv row for New_Analysis_Set_07 (for the separate issue you flagged) =====")
record_path = os.path.join(PROJECT_ROOT, "analysis_set_record.csv")
with open(record_path, "r", encoding="utf-8") as f:
    lines = f.readlines()
print("Header:", lines[0].strip())
for line in lines[1:]:
    if line.startswith("New_Analysis_Set_07,"):
        print("Row:   ", line.strip())
