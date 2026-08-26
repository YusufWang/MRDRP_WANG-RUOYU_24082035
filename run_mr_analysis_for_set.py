"""
run_mr_analysis_for_set.py

Background launcher for running mr_pipeline.run_pipeline_for_analysis_set()
as a genuine, detached OS process -- meant to be started by app.py's "Run
MR analysis" button via subprocess.Popen(..., start_new_session=True), NOT
run interactively.

Because it's a real background process (not tied to the Streamlit
websocket session), it keeps running even if the browser tab is closed or
the dashboard itself is restarted -- as long as the underlying server
stays up. Progress is written to a JSON file next to the analysis set's
other outputs, which the dashboard polls to show a live progress bar.

Usage (called by app.py, not typically run by hand):
    python3 run_mr_analysis_for_set.py "My_Analysis_Set_01"

Expects OPENGWAS_JWT to already be set in the environment (passed in by
the launching process) -- same requirement as mr_pipeline.ld_clump().
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path("/home/owner/wangruoyu_wqf7023_mrdrp/MRDRP-main")
if not PROJECT_ROOT.exists():
    # Fall back to wherever this script itself lives, so it also works if
    # the project folder ever moves.
    PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def _write_progress(progress_path: Path, **fields) -> None:
    """
    Atomic-ish write: build the full dict, write to a temp file, then
    rename over the real path -- so the dashboard polling this file never
    sees a half-written JSON blob, even if it reads at an awkward moment.
    """
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = progress_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(fields, f)
    tmp_path.replace(progress_path)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 run_mr_analysis_for_set.py <analysis_set_name>")
        sys.exit(1)

    analysis_set_name = sys.argv[1]

    import re
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", analysis_set_name)
    set_dir = PROJECT_ROOT / "backend_work" / "mr_outputs_by_set" / safe_name
    progress_path = set_dir / "_run_progress.json"
    log_path = set_dir / "_run_log.txt"
    set_dir.mkdir(parents=True, exist_ok=True)

    started_at = time.time()
    _write_progress(
        progress_path,
        status="running", fraction=0.0, message="Starting up...",
        started_at=started_at, updated_at=time.time(),
        pid=os.getpid(), error=None,
    )

    # Redirect stdout/stderr to a log file for later inspection -- this
    # captures every print() already inside mr_pipeline.py, separate from
    # the structured JSON progress file the UI actually polls.
    log_file = open(log_path, "w", encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = log_file

    try:
        if not os.environ.get("OPENGWAS_JWT", "").strip():
            raise RuntimeError(
                "OPENGWAS_JWT is not set in this process's environment. "
                "The launching process must pass it in explicitly."
            )

        print(f"[run_mr_analysis_for_set] Starting analysis set '{analysis_set_name}' (PID {os.getpid()})")
        print(f"[run_mr_analysis_for_set] PROJECT_ROOT: {PROJECT_ROOT}")

        os.environ.setdefault("R_HOME", "")
        if not os.environ["R_HOME"]:
            import subprocess
            try:
                r_home = subprocess.run(["R", "RHOME"], capture_output=True, text=True, check=True).stdout.strip()
                os.environ["R_HOME"] = r_home
                print(f"[run_mr_analysis_for_set] R_HOME was not set -- detected and set to: {r_home}")
            except Exception as e:
                print(f"[run_mr_analysis_for_set] WARNING: could not auto-detect R_HOME: {e}")

        import mr_pipeline

        def progress_callback(fraction: float, message: str) -> None:
            _write_progress(
                progress_path,
                status="running", fraction=fraction, message=message,
                started_at=started_at, updated_at=time.time(),
                pid=os.getpid(), error=None,
            )

        result = mr_pipeline.run_pipeline_for_analysis_set(
            analysis_set_name, progress_callback=progress_callback,
        )

        n_results = len(result["combined_results"])
        n_significant = 0
        if n_results > 0 and "pval" in result["combined_results"].columns:
            n_significant = int((result["combined_results"]["pval"] < 0.05).sum())

        _write_progress(
            progress_path,
            status="completed", fraction=1.0,
            message=f"Done -- {n_results} MR result row(s), {n_significant} nominally significant (p<0.05).",
            started_at=started_at, updated_at=time.time(),
            pid=os.getpid(), error=None,
        )
        print(f"[run_mr_analysis_for_set] Completed successfully. {n_results} result row(s).")

    except Exception as e:
        error_text = f"{e}\n\n{traceback.format_exc()}"
        print(f"[run_mr_analysis_for_set] FAILED: {error_text}")
        _write_progress(
            progress_path,
            status="failed", fraction=None, message=f"Failed: {e}",
            started_at=started_at, updated_at=time.time(),
            pid=os.getpid(), error=error_text,
        )
        sys.exit(1)

    finally:
        log_file.close()


if __name__ == "__main__":
    main()
