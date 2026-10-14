"""Download raw data files listed in sources.py into data/raw/.

Sources are grouped by state (LA, IL, NJ, ...) or national source (FSA, CCD).

Usage (from the repository root):
    python code/00_download_raw_data.py                 # all registered groups
    python code/00_download_raw_data.py LA IL FSA       # selected groups
    python code/00_download_raw_data.py NJ --force      # re-download existing files
    python code/00_download_raw_data.py --dry-run       # list what would be fetched

Files are saved to data/raw/<state>/<source_id>/<filename>, with national
sources under data/raw/US/. Every download is
recorded in data/raw/download_manifest.csv with its URL, access time (UTC),
size, SHA-256, and the server's Last-Modified header. On --force, a changed
hash means the publisher silently replaced the file; it is reported so the
change can be investigated instead of overwritten unnoticed.

Uses only the Python standard library.
"""

import argparse
import csv
import hashlib
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from http_utils import CHUNK, RETRIES, open_url
from sources import SOURCES

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "download_manifest.csv"
MANIFEST_FIELDS = [
    "state", "source_id", "year_label", "kind", "local_path", "url",
    "accessed_utc", "bytes", "sha256", "last_modified", "status", "note",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url, dest):
    """Stream url to dest via a .part file. Returns the Last-Modified header."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, RETRIES + 1):
        try:
            with open_url(url) as r, open(tmp, "wb") as f:
                last_modified = r.headers.get("Last-Modified", "")
                while block := r.read(CHUNK):
                    f.write(block)
            tmp.replace(dest)
            return last_modified
        except urllib.error.HTTPError:
            tmp.unlink(missing_ok=True)
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            tmp.unlink(missing_ok=True)
            if attempt == RETRIES:
                raise
            print(f"    retry {attempt}/{RETRIES - 1} after {type(e).__name__}: {e}")


def load_manifest():
    if not MANIFEST.exists():
        return {}
    with open(MANIFEST, newline="") as f:
        return {row["local_path"]: row for row in csv.DictReader(f)}


def save_manifest(rows):
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for key in sorted(rows):
            w.writerow(rows[key])


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("groups", nargs="*", default=sorted(SOURCES),
                        help=f"groups to download (default: all of {sorted(SOURCES)})")
    parser.add_argument("--force", action="store_true",
                        help="re-download files that already exist")
    parser.add_argument("--dry-run", action="store_true",
                        help="list files without downloading")
    args = parser.parse_args()

    unknown = [g for g in args.groups if g.upper() not in SOURCES]
    if unknown:
        parser.error(f"no sources registered for {unknown}; known: {sorted(SOURCES)}")

    manifest = load_manifest()
    failures, changed = [], []

    for group in (g.upper() for g in args.groups):
        # Some groups read their file list from the publisher's site.
        try:
            sources = SOURCES[group]()
        except Exception as e:
            print(f"[{group}] FAILED to build file list: {type(e).__name__}: {e}")
            failures.append((group, f"file list: {e}"))
            continue
        for src in sources:
            dest = RAW / src.state / src.source_id / src.filename
            rel = dest.relative_to(ROOT).as_posix()
            label = f"[{src.state}] {src.year_label or '-':>9} {src.kind:<6} {src.filename}"

            if args.dry_run:
                print(f"{label}\n    {src.url}")
                continue
            # HTML snapshots are always refreshed: they record what the
            # publisher listed on the access date.
            if dest.exists() and not args.force and src.kind != "page":
                print(f"{label}  (exists, skipped)")
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            old_hash = manifest.get(rel, {}).get("sha256", "")
            print(f"{label}  downloading...")
            try:
                last_modified = fetch(src.url, dest)
            except urllib.error.HTTPError as e:
                if src.optional and e.code == 404:
                    print(f"    not posted (404), optional")
                    continue
                print(f"    FAILED: HTTP {e.code}")
                failures.append((rel, f"HTTP {e.code}"))
                continue
            except Exception as e:
                print(f"    FAILED: {type(e).__name__}: {e}")
                failures.append((rel, str(e)))
                continue

            digest = sha256(dest)
            status = "downloaded"
            if old_hash and old_hash != digest:
                status = "changed"
                if src.kind != "page":
                    changed.append(rel)
            manifest[rel] = {
                "state": src.state, "source_id": src.source_id,
                "year_label": src.year_label, "kind": src.kind,
                "local_path": rel, "url": src.url,
                "accessed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "bytes": dest.stat().st_size, "sha256": digest,
                "last_modified": last_modified, "status": status, "note": src.note,
            }
            print(f"    {dest.stat().st_size:,} bytes  sha256 {digest[:12]}")
            # Save after each file so an interrupted run keeps its record.
            save_manifest(manifest)

    if changed:
        print("\nWARNING: these files differ from the previously recorded version:")
        for rel in changed:
            print(f"  {rel}")
    if failures:
        print("\nFailed downloads:")
        for rel, err in failures:
            print(f"  {rel}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
