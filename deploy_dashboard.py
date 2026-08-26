"""
deploy_dashboard.py

Sets up the full MRDRP dashboard on this server: Streamlit + a branded
HTML wrapper page (header, icon, embedded iframe) + two persistent
Cloudflare tunnels -- everything running inside tmux sessions so it
survives AnyDesk disconnects. Mirrors the Colab workflow this project has
used throughout (same index.html layout, same two-tunnel structure), with
two deliberate differences explained inline below.

Run with (inside the activated wqf7023_mrdrp conda env):
    python3 deploy_dashboard.py
"""
import subprocess
import time
import re
from pathlib import Path

PROJECT_ROOT = Path("/home/owner/wangruoyu_wqf7023_mrdrp/MRDRP-main")
CLOUDFLARED_BIN = Path.home() / "bin" / "cloudflared"

STREAMLIT_LOG = Path.home() / "streamlit_dashboard.log"
TUNNEL_STREAMLIT_LOG = Path.home() / "cloudflared_tunnel_streamlit.log"
HTMLSERVER_LOG = Path.home() / "html_server.log"
TUNNEL_HTML_LOG = Path.home() / "cloudflared_tunnel_html.log"


def get_conda_base() -> str:
    result = subprocess.run(["conda", "info", "--base"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def tmux_session(name: str, command: str) -> None:
    """(Re)start a detached tmux session running `command`. Kills only the
    named session it manages, not a blanket pkill -- this machine is a
    SHARED lab account, so killing anything matching 'streamlit' or
    'cloudflared' machine-wide (as the Colab version did, which was safe
    there since each notebook has its own isolated compute instance) risks
    killing another lab member's process here."""
    subprocess.run(["tmux", "kill-session", "-t", name], capture_output=True)
    subprocess.run(["tmux", "new-session", "-d", "-s", name, command], check=True)
    print(f"tmux session '{name}' started.")


def extract_trycloudflare_url(log_path: Path, wait_seconds: int = 8) -> str:
    time.sleep(wait_seconds)
    text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    print(text)
    urls = re.findall(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com", text)
    if not urls:
        raise RuntimeError(
            f"No trycloudflare URL found in {log_path} yet. Wait a few seconds and run this script "
            "again, or check the log file directly for errors."
        )
    return urls[0]


def build_index_html(streamlit_url: str) -> Path:
    html_path = PROJECT_ROOT / "index.html"
    icon_file = PROJECT_ROOT / "MR-Icon.png"
    if not icon_file.exists():
        print("WARNING: MR-Icon.png was not found at:", icon_file)
    else:
        print("MR-Icon.png found:", icon_file)

    html_code = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MRDRP Targeted Dashboard Web Service</title>

    <link rel="icon" type="image/png" href="MR-Icon.png">
    <link rel="shortcut icon" type="image/png" href="MR-Icon.png">
    <link rel="apple-touch-icon" href="MR-Icon.png">

    <style>
        body {{
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            background: #DDE4E1;
            color: #24312D;
        }}

        header {{
            background: #1F6F5F;
            color: white;
            padding: 14px 24px;
            display: flex;
            align-items: center;
            gap: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}

        .logo {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            object-fit: cover;
            background: white;
            padding: 3px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.18);
        }}

        .title-block {{
            display: flex;
            flex-direction: column;
        }}

        .title {{
            font-size: 22px;
            font-weight: bold;
            line-height: 1.2;
        }}

        .subtitle {{
            font-size: 14px;
            font-weight: normal;
            margin-top: 5px;
            color: #EAF2EE;
        }}

        iframe {{
            width: 100%;
            height: calc(100vh - 78px);
            border: none;
            display: block;
        }}
    </style>
</head>

<body>
    <header>
        <img src="MR-Icon.png" alt="MRDRP logo" class="logo">

        <div class="title-block">
            <div class="title">MRDRP Targeted Dashboard Web Service</div>
            <div class="subtitle">
                Embedded Streamlit dashboard for targeted GWAS screening, backend MR results, and multi-outcome comparison
            </div>
        </div>
    </header>

    <iframe src="{streamlit_url}"></iframe>
</body>
</html>
"""
    html_path.write_text(html_code, encoding="utf-8")
    return html_path


def main():
    conda_base = get_conda_base()

    print("=" * 60)
    print("Step 1: Start Streamlit")
    print("=" * 60)
    # NOTE: unlike the Colab version, this does NOT run 'pip install streamlit
    # pyliftover' first -- those are already installed in the wqf7023_mrdrp
    # conda env (confirmed earlier), and this environment persists across
    # restarts, unlike Colab which wipes its environment every session.
    streamlit_cmd = (
        f"source {conda_base}/etc/profile.d/conda.sh && conda activate wqf7023_mrdrp && "
        f"export R_HOME=$(R RHOME) && cd {PROJECT_ROOT} && "
        f"streamlit run app.py --server.port 8501 --server.headless true > {STREAMLIT_LOG} 2>&1"
    )
    tmux_session("mrdrp_dashboard", streamlit_cmd)
    print("Waiting for Streamlit to come up...")
    time.sleep(6)
    print(STREAMLIT_LOG.read_text(encoding="utf-8", errors="ignore") if STREAMLIT_LOG.exists() else "(no log yet)")

    check = subprocess.run("curl -sI http://localhost:8501", shell=True, capture_output=True, text=True)
    print(check.stdout)

    print()
    print("=" * 60)
    print("Step 2: Tunnel Streamlit itself (internal link, not the one you share)")
    print("=" * 60)
    tmux_session(
        "mrdrp_tunnel_streamlit",
        f"{CLOUDFLARED_BIN} tunnel --url http://localhost:8501 > {TUNNEL_STREAMLIT_LOG} 2>&1",
    )
    streamlit_url = extract_trycloudflare_url(TUNNEL_STREAMLIT_LOG)
    print("Internal Streamlit URL:", streamlit_url)

    print()
    print("=" * 60)
    print("Step 3: Build the branded index.html wrapping that URL in an iframe")
    print("=" * 60)
    html_path = build_index_html(streamlit_url)
    print("index.html created:", html_path)

    print()
    print("=" * 60)
    print("Step 4: Serve index.html (and MR-Icon.png) via a local HTTP server")
    print("=" * 60)
    tmux_session(
        "mrdrp_htmlserver",
        f"cd {PROJECT_ROOT} && python3 -m http.server 8000 > {HTMLSERVER_LOG} 2>&1",
    )
    time.sleep(3)

    print()
    print("=" * 60)
    print("Step 5: Tunnel the HTML server (THIS is the link to share/bookmark)")
    print("=" * 60)
    tmux_session(
        "mrdrp_tunnel_html",
        f"{CLOUDFLARED_BIN} tunnel --url http://localhost:8000 > {TUNNEL_HTML_LOG} 2>&1",
    )
    html_url = extract_trycloudflare_url(TUNNEL_HTML_LOG)

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print("Share/bookmark this link (branded page with the dashboard embedded):")
    print(html_url)
    print()
    print("(Internal Streamlit-only link, for reference:", streamlit_url, ")")
    print()
    print("tmux sessions running: mrdrp_dashboard, mrdrp_tunnel_streamlit, mrdrp_htmlserver, mrdrp_tunnel_html")
    print("To stop everything:")
    print(
        "  tmux kill-session -t mrdrp_dashboard; tmux kill-session -t mrdrp_tunnel_streamlit; "
        "tmux kill-session -t mrdrp_htmlserver; tmux kill-session -t mrdrp_tunnel_html"
    )


if __name__ == "__main__":
    main()
