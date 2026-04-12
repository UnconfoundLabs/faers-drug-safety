"""
FAERS Drug Safety Pipeline — Step 01: Download Quarterly Data
Downloads FAERS ASCII quarterly extracts from FDA and unzips them.
"""

import os
import zipfile
import requests
from tqdm import tqdm

# ── Configuration ────────────────────────────────────────────────────────────
RAW_DIR = os.path.expanduser("~/faers-drug-safety/data/raw")
os.makedirs(RAW_DIR, exist_ok=True)

# Quarters to download (start small — 2 quarters)
QUARTERS = [
    "2024Q3",
    "2024Q4",
]

BASE_URL = "https://fis.fda.gov/content/Exports/faers_ascii_{quarter}.zip"


def download_file(url: str, dest: str) -> bool:
    """Download a file with progress bar. Returns True if successful."""
    if os.path.exists(dest):
        print(f"  Already exists: {os.path.basename(dest)}")
        return True

    print(f"  Downloading: {url}")
    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: {e}")
        return False

    total = int(resp.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(
        total=total, unit="B", unit_scale=True, desc=os.path.basename(dest)
    ) as pbar:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            pbar.update(len(chunk))

    return True


def unzip_quarter(zip_path: str, quarter: str) -> str:
    """Unzip a quarterly file into its own directory. Returns extract dir."""
    extract_dir = os.path.join(RAW_DIR, quarter)
    if os.path.exists(extract_dir) and any(
        f.endswith(".txt") for f in os.listdir(extract_dir)
    ):
        print(f"  Already extracted: {quarter}/")
        return extract_dir

    print(f"  Extracting: {os.path.basename(zip_path)}")
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        # FAERS zips sometimes have nested directories — extract all
        zf.extractall(extract_dir)

    # Move files out of any nested subdir to the quarter dir
    for root, dirs, files in os.walk(extract_dir):
        if root == extract_dir:
            continue
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(extract_dir, fname)
            if not os.path.exists(dst):
                os.rename(src, dst)

    print(f"  Files in {quarter}/:")
    for f in sorted(os.listdir(extract_dir)):
        if f.endswith(".txt"):
            size_mb = os.path.getsize(os.path.join(extract_dir, f)) / 1e6
            print(f"    {f:40s} {size_mb:>8.1f} MB")

    return extract_dir


def main():
    print("=" * 60)
    print("FAERS Download — Step 01")
    print("=" * 60)

    for quarter in QUARTERS:
        print(f"\n── {quarter} ──")
        url = BASE_URL.format(quarter=quarter)
        zip_path = os.path.join(RAW_DIR, f"faers_ascii_{quarter}.zip")

        if download_file(url, zip_path):
            unzip_quarter(zip_path, quarter)
            # Delete zip to save disk space
            if os.path.exists(zip_path):
                os.remove(zip_path)
                print(f"  Deleted zip to save space")

    print("\n" + "=" * 60)
    print("Download complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
