from pathlib import Path
import shutil
from datetime import datetime
import pandas as pd

PROJECT_ROOT = Path("/home/owner/wangruoyu_wqf7023_mrdrp/MRDRP-main")
OLD_PREFIX = "/content/drive/MyDrive/UM_WQF7023/MRDRP-main"
NEW_PREFIX = str(PROJECT_ROOT)

record_path = PROJECT_ROOT / "artesunate_file_screening_record.csv"

backup_path = PROJECT_ROOT / f"artesunate_file_screening_record_backup_before_path_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
shutil.copy2(record_path, backup_path)
print("Backup created:")
print(backup_path)

df = pd.read_csv(record_path)
print(f"\nLoaded {len(df)} row(s) from {record_path.name}")

if "file_path" not in df.columns:
    print("No 'file_path' column found -- nothing to update.")
else:
    mask = df["file_path"].astype(str).str.startswith(OLD_PREFIX)
    n_updated = int(mask.sum())
    df.loc[mask, "file_path"] = df.loc[mask, "file_path"].astype(str).str.replace(OLD_PREFIX, NEW_PREFIX, regex=False)
    df.to_csv(record_path, index=False)
    print(f"Updated {n_updated} / {len(df)} file_path value(s) from the old Colab prefix to this server's path.")

    exists_count = int(df["file_path"].apply(lambda p: Path(str(p)).exists()).sum())
    print(f"\nVerification: {exists_count} / {len(df)} file_path value(s) now point to files that actually exist on this machine.")
    if exists_count < len(df):
        print("Some paths still don't resolve -- printing those rows for a closer look:")
        missing = df[~df["file_path"].apply(lambda p: Path(str(p)).exists())]
        print(missing[["file_name", "file_path"]].to_string())
