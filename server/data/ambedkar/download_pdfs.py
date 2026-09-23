"""
PDF Downloader for Dr. B. R. Ambedkar Writings & Speeches
==========================================================
Downloads official PDFs from https://www.drambedkarwritings.gov.in/

Usage:
    python server/data/ambedkar/download_pdfs.py
"""

import os
import sys
import json
import time
import urllib3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Suppress InsecureRequestWarning — the .gov.in SSL cert is expired
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Configuration ────────────────────────────────────────────
BASE_URL = "https://www.drambedkarwritings.gov.in/upload/uploadfiles/files/"
WRITINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "writings")
METADATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# Known volume patterns from the official website
# Volumes 1–21, with some volumes split into parts
VOLUME_PATTERNS = []

# Single volumes: Volume_01.pdf through Volume_21.pdf
for i in range(1, 22):
    VOLUME_PATTERNS.append(f"Volume_{i:02d}.pdf")

# Split volumes (known splits based on official website structure)
# Volume 17 is confirmed to have parts
for vol in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]:
    for part in range(1, 5):  # Up to 4 parts
        filename = f"Volume_{vol:02d}_{part:02d}.pdf"
        if filename not in VOLUME_PATTERNS:
            VOLUME_PATTERNS.append(filename)

# Also try without zero-padding (some gov sites use inconsistent naming)
for i in range(1, 22):
    alt = f"Volume_{i}.pdf"
    if alt not in VOLUME_PATTERNS:
        VOLUME_PATTERNS.append(alt)

# Connection settings — government servers can be very slow
CONNECT_TIMEOUT = 60   # seconds
READ_TIMEOUT = 300     # seconds (5 minutes — PDFs can be large)
MAX_RETRIES = 3
BACKOFF_FACTOR = 2     # exponential: 2s, 4s, 8s


def create_session():
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def is_valid_pdf(filepath):
    """Check if a file starts with the PDF signature %PDF."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(5)
            return header.startswith(b"%PDF")
    except Exception:
        return False


def download_pdf(session, filename, results):
    """
    Attempt to download a single PDF.
    Returns the status: 'downloaded', 'already_exists', 'unavailable', 'failed'
    """
    url = BASE_URL + filename
    filepath = os.path.join(WRITINGS_DIR, filename)

    # Skip if already downloaded and valid
    if os.path.exists(filepath) and is_valid_pdf(filepath):
        file_size = os.path.getsize(filepath)
        if file_size > 1000:  # Must be more than 1KB to be a real PDF
            print(f"  ✓ ALREADY EXISTS: {filename} ({file_size:,} bytes)")
            results.append({
                "filename": filename,
                "status": "already_exists",
                "size_bytes": file_size,
            })
            return "already_exists"

    # Attempt download
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  ↓ Downloading: {filename} (attempt {attempt}/{MAX_RETRIES})...", end="", flush=True)
            # Try normal HTTPS certificate verification first
            try:
                response = session.get(
                    url,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    verify=True,
                    stream=True,
                )
            except (requests.exceptions.SSLError, urllib3.exceptions.SSLError) as ssl_err:
                # Documented fallback when official government server certificate verification fails
                print(f" [SSL Verification Failed: using verify=False fallback]...", end="", flush=True)
                response = session.get(
                    url,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    verify=False,
                    stream=True,
                )

            if response.status_code == 404:
                print(f" NOT FOUND (404)")
                results.append({
                    "filename": filename,
                    "status": "unavailable",
                    "reason": "HTTP 404",
                })
                return "unavailable"

            if response.status_code != 200:
                print(f" HTTP {response.status_code}")
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_FACTOR ** attempt
                    print(f"    Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                results.append({
                    "filename": filename,
                    "status": "failed",
                    "reason": f"HTTP {response.status_code}",
                })
                return "failed"

            # Check content type
            content_type = response.headers.get("Content-Type", "")
            if "html" in content_type.lower():
                # Server returned an HTML error page, not a PDF
                print(f" HTML response (not a PDF)")
                results.append({
                    "filename": filename,
                    "status": "unavailable",
                    "reason": "Server returned HTML instead of PDF",
                })
                return "unavailable"

            # Download content
            content = response.content

            # Verify PDF signature
            if not content.startswith(b"%PDF"):
                print(f" INVALID (not a PDF)")
                results.append({
                    "filename": filename,
                    "status": "unavailable",
                    "reason": "Response does not contain PDF signature",
                })
                return "unavailable"

            # Check minimum size
            if len(content) < 1000:
                print(f" TOO SMALL ({len(content)} bytes)")
                results.append({
                    "filename": filename,
                    "status": "unavailable",
                    "reason": f"File too small ({len(content)} bytes)",
                })
                return "unavailable"

            # Save the PDF
            with open(filepath, "wb") as f:
                f.write(content)

            file_size = len(content)
            print(f" OK ({file_size:,} bytes)")
            results.append({
                "filename": filename,
                "status": "downloaded",
                "size_bytes": file_size,
            })
            return "downloaded"

        except requests.exceptions.Timeout:
            print(f" TIMEOUT")
            if attempt < MAX_RETRIES:
                wait = BACKOFF_FACTOR ** attempt
                print(f"    Retrying in {wait}s...")
                time.sleep(wait)
            else:
                results.append({
                    "filename": filename,
                    "status": "failed",
                    "reason": "Timeout after all retries",
                })
                return "failed"

        except requests.exceptions.ConnectionError as e:
            print(f" CONNECTION ERROR")
            if attempt < MAX_RETRIES:
                wait = BACKOFF_FACTOR ** attempt
                print(f"    Retrying in {wait}s...")
                time.sleep(wait)
            else:
                results.append({
                    "filename": filename,
                    "status": "failed",
                    "reason": f"Connection error: {str(e)[:100]}",
                })
                return "failed"

        except Exception as e:
            print(f" ERROR: {e}")
            results.append({
                "filename": filename,
                "status": "failed",
                "reason": str(e)[:200],
            })
            return "failed"

    results.append({
        "filename": filename,
        "status": "failed",
        "reason": "Exhausted all retries",
    })
    return "failed"


def main():
    print("=" * 70)
    print("  Dr. B. R. Ambedkar — Writings & Speeches PDF Downloader")
    print("  Source: https://www.drambedkarwritings.gov.in/")
    print("=" * 70)
    print()

    # Create output directory
    os.makedirs(WRITINGS_DIR, exist_ok=True)

    session = create_session()
    results = []

    # Track unique filenames to avoid duplicates
    tried = set()

    print(f"Checking {len(VOLUME_PATTERNS)} potential PDF URLs...\n")

    for filename in VOLUME_PATTERNS:
        if filename in tried:
            continue
        tried.add(filename)
        download_pdf(session, filename, results)

    # ── Summary Report ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("  DOWNLOAD REPORT")
    print("=" * 70)

    downloaded = [r for r in results if r["status"] == "downloaded"]
    existing = [r for r in results if r["status"] == "already_exists"]
    unavailable = [r for r in results if r["status"] == "unavailable"]
    failed = [r for r in results if r["status"] == "failed"]

    print(f"\n  ✅ Downloaded:     {len(downloaded)}")
    print(f"  📁 Already exists: {len(existing)}")
    print(f"  ❌ Unavailable:    {len(unavailable)}")
    print(f"  ⚠️  Failed:         {len(failed)}")
    print(f"  📊 Total checked:  {len(results)}")

    if downloaded:
        print("\n  Newly downloaded:")
        for r in downloaded:
            size_mb = r.get("size_bytes", 0) / (1024 * 1024)
            print(f"    • {r['filename']} ({size_mb:.1f} MB)")

    if existing:
        print("\n  Already had:")
        for r in existing:
            size_mb = r.get("size_bytes", 0) / (1024 * 1024)
            print(f"    • {r['filename']} ({size_mb:.1f} MB)")

    if failed:
        print("\n  Failed downloads:")
        for r in failed:
            print(f"    • {r['filename']}: {r.get('reason', 'unknown')}")

    # ── Save metadata.json ──────────────────────────────────
    successful = [r for r in results if r["status"] in ("downloaded", "already_exists")]
    metadata_entries = []
    for r in successful:
        # Parse volume info from filename
        fname = r["filename"]
        vol_str = fname.replace("Volume_", "").replace(".pdf", "")
        if "_" in vol_str:
            parts = vol_str.split("_")
            volume_label = f"Volume {int(parts[0])}, Part {int(parts[1])}"
        else:
            volume_label = f"Volume {int(vol_str)}"

        metadata_entries.append({
            "filename": fname,
            "source": "Dr. Ambedkar Writings and Speeches",
            "official_url": BASE_URL + fname,
            "volume": volume_label,
            "download_status": "success",
        })

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata_entries, f, indent=2, ensure_ascii=False)

    print(f"\n  📄 Metadata saved to: {METADATA_PATH}")
    print(f"  📂 PDFs directory:    {WRITINGS_DIR}")

    total_available = len(downloaded) + len(existing)
    print(f"\n  🎯 Total PDFs available for RAG: {total_available}")
    print("=" * 70)

    return total_available


if __name__ == "__main__":
    count = main()
    if count == 0:
        print("\n⚠️  No PDFs were downloaded. Check your internet connection.")
        print("   The government server may be temporarily unavailable.")
        sys.exit(1)
    else:
        print(f"\n✅ Ready! Run 'python server/rag/ingest.py' to build the RAG index.")
