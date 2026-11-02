"""Download raw data files listed in sources.py into data/raw/.

Sources are grouped by state (LA, IL, NJ, ...) or national source (FSA, CCD).

Usage (from the repository root):
    uv run --locked python code/00_download_raw_data.py                 # all registered groups
    uv run --locked python code/00_download_raw_data.py LA IL FSA       # selected groups
    uv run --locked python code/00_download_raw_data.py NJ --force      # re-download existing files
    uv run --locked python code/00_download_raw_data.py --dry-run       # list what would be fetched
    uv run --locked python code/00_download_raw_data.py --check         # check files already downloaded
    uv run --locked python code/00_download_raw_data.py --prune         # drop manifest rows of deleted files

Each new file is checked before it is kept: binary types must start with
their signature (.xlsx/.zip "PK", .xls OLE2, .pdf "%PDF") and text types
(.csv/.txt/.json) must not be an HTML page. A mismatch counts as a failed
download, since servers sometimes return an error page with status 200.

Manual sources (Source.manual: the publisher blocks scripts, so the files are
exported by hand in a browser) are never fetched. A present manual file is
recorded in the manifest with its hash; a missing one is reported with its
export steps and counts as a failure; --check also flags a manual file whose
hash no longer matches the manifest.

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

from config import OUTPUT, RAW, ROOT
from sources import CATALOG, CATALOG_FIELDS, CHUNK, RETRIES, SOURCES, open_url

# One row per downloaded file, keyed by its repository-relative path.
MANIFEST = RAW / "download_manifest.csv"
# One row per state x measure: where it comes from and whether it is scripted.
CATALOG_CSV = OUTPUT / "tables" / "state_data_sources.csv"
MANIFEST_FIELDS = [
    "state", "source_id", "year_label", "kind", "local_path", "url",
    "accessed_utc", "bytes", "sha256", "last_modified", "status", "note",
]


def sha256(path):
    """Return the SHA-256 hex digest of a file, read in CHUNK-sized blocks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


# Leading bytes each binary file type must start with. Servers sometimes answer
# a bad request with an HTML page and status 200 (CDE's bot check, THECB for a
# missing year, a failed ALSDE form post); this catches those.
SIGNATURES = {
    ".xlsx": (b"PK\x03\x04",),
    ".zip": (b"PK\x03\x04",),
    ".xls": (b"\xd0\xcf\x11\xe0",),   # OLE2 (BIFF) workbook
    ".pdf": (b"%PDF",),
}
TEXT_TYPES = {".csv", ".txt", ".json"}  # must not be an HTML page


class ContentError(Exception):
    """A downloaded file's content does not match its extension."""


def content_problem(path, suffix=None):
    """Return why a file's first bytes don't match its type, or None if they do.

    suffix overrides the path's extension (used for .part files).
    """
    suffix = (suffix or path.suffix).lower()
    with open(path, "rb") as f:
        head = f.read(512)
    if not head:
        return "empty file"
    if suffix in SIGNATURES and not head.startswith(SIGNATURES[suffix]):
        return f"not a {suffix} file (starts with {head[:15]!r})"
    if suffix in TEXT_TYPES and head.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        return "HTML page instead of data"
    return None


def fetch(src, dest):
    """Stream a Source to dest via a .part file and check its content.

    Returns the Last-Modified header. Uses src.fetch() when the Source needs a
    form post or session, else a GET of src.url. Raises ContentError (and keeps
    nothing) if the file does not look like its extension.
    """
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, RETRIES + 1):
        try:
            with (src.fetch() if src.fetch else open_url(src.url)) as r, open(tmp, "wb") as f:
                last_modified = r.headers.get("Last-Modified", "")
                while block := r.read(CHUNK):
                    f.write(block)
            if src.kind != "page" and (problem := content_problem(tmp, dest.suffix)):
                tmp.unlink()
                raise ContentError(problem)
            # Only a complete, checked download replaces dest, so a failure
            # never leaves a truncated or wrong file behind.
            tmp.replace(dest)
            return last_modified
        except urllib.error.HTTPError:
            # HTTP errors (404, 403, ...) won't fix themselves; don't retry.
            tmp.unlink(missing_ok=True)
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            tmp.unlink(missing_ok=True)
            if attempt == RETRIES:
                raise
            print(f"    retry {attempt}/{RETRIES - 1} after {type(e).__name__}: {e}")


def load_manifest():
    """Read the download manifest into {local_path: row}; empty if none exists yet."""
    if not MANIFEST.exists():
        return {}
    with open(MANIFEST, newline="") as f:
        return {row["local_path"]: row for row in csv.DictReader(f)}


def save_manifest(rows):
    """Write all manifest rows, sorted by local path so diffs stay stable."""
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for key in sorted(rows):
            w.writerow(rows[key])


def check_existing(manifest):
    """Check every data/doc file already in the manifest; print and return problems.

    Manual exports can't be re-downloaded, so they must also be present and
    unchanged (same SHA-256 as recorded).
    """
    problems = []
    for rel, row in sorted(manifest.items()):
        path = ROOT / rel
        manual = row["status"] == "manual"
        if manual and not path.exists():
            problems.append((rel, "manual export missing"))
            continue
        if row["kind"] == "page" or not path.exists():
            continue
        if problem := content_problem(path):
            problems.append((rel, problem))
        elif manual and sha256(path) != row["sha256"]:
            problems.append((rel, "manual export changed since it was recorded"))
    print(f"Checked {sum(r['kind'] != 'page' for r in manifest.values()):,} files in the manifest: "
          f"{len(problems)} problem(s)")
    for rel, problem in problems:
        print(f"  {rel}: {problem}")
    return problems


def record_manual(src, dest, rel, manifest, failures, label):
    """Register a hand-exported file: add it to the manifest (hash, file time)
    if new, or report it missing with its export steps."""
    if not dest.exists():
        print(f"{label}  MISSING manual export: {src.note}\n    {src.url}")
        failures.append((rel, "manual export missing (see docs/source-notes.md)"))
        return
    if rel in manifest:
        print(f"{label}  (manual, recorded)")
        return
    if problem := content_problem(dest):
        failures.append((rel, problem))
        return
    stat = dest.stat()
    manifest[rel] = {
        "state": src.state, "source_id": src.source_id, "year_label": src.year_label,
        "kind": src.kind, "local_path": rel, "url": src.url,
        # The export time (file modification time) stands in for the access time.
        "accessed_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        "bytes": stat.st_size, "sha256": sha256(dest), "last_modified": "",
        "status": "manual", "note": src.note,
    }
    print(f"{label}  manual export recorded")
    save_manifest(manifest)


def prune(manifest):
    """Remove manifest rows whose file is no longer on disk (files deleted by hand,
    e.g. sources dropped from SOURCES). Manual exports are kept: a missing one is
    an error that --check reports. Prints and saves the result."""
    gone = sorted(rel for rel, row in manifest.items()
                  if row["status"] != "manual" and not (ROOT / rel).exists())
    for rel in gone:
        print(f"  pruned {rel}")
        del manifest[rel]
    save_manifest(manifest)
    print(f"Pruned {len(gone)} manifest row(s) for files no longer on disk; {len(manifest):,} remain")


def write_catalog():
    """Write the source catalog (sources.CATALOG) to output/tables/state_data_sources.csv."""
    CATALOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CATALOG_FIELDS)
        w.writerows(CATALOG)
    print(f"Wrote {CATALOG_CSV.relative_to(ROOT)} ({len(CATALOG)} state x measure rows)")


def main():
    """Parse arguments, download each selected group's files, and update the manifest.

    Exits with status 1 if any download (or file-list build) failed.
    """
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("groups", nargs="*", default=sorted(SOURCES),
                        help=f"groups to download (default: all of {sorted(SOURCES)})")
    parser.add_argument("--force", action="store_true",
                        help="re-download files that already exist")
    parser.add_argument("--dry-run", action="store_true",
                        help="list files without downloading")
    parser.add_argument("--check", action="store_true",
                        help="only check that downloaded files match their type, then exit")
    parser.add_argument("--prune", action="store_true",
                        help="only remove manifest rows for files no longer on disk, then exit")
    args = parser.parse_args()
    if args.check:
        sys.exit(1 if check_existing(load_manifest()) else 0)
    if args.prune:
        prune(load_manifest())
        return

    unknown = [g for g in args.groups if g.upper() not in SOURCES]
    if unknown:
        parser.error(f"no sources registered for {unknown}; known: {sorted(SOURCES)}")

    write_catalog()
    manifest = load_manifest()
    failures, changed = [], []  # (path, error) pairs; paths whose hash changed

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
            if src.manual:
                record_manual(src, dest, rel, manifest, failures, label)
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
                last_modified = fetch(src, dest)
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

            # Compare with the hash recorded last time to catch files the
            # publisher replaced without changing the URL.
            digest = sha256(dest)
            status = "downloaded"
            if old_hash and old_hash != digest:
                status = "changed"
                # Snapshot pages change routinely; only flag data/doc files.
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
