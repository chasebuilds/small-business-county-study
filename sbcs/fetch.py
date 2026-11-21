"""Download raw files into data/raw/ and verify them against data/checksums.json."""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

from .sources import sources

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CHECKSUMS = ROOT / "data" / "checksums.json"
USER_AGENT = "chase-builds-small-business-county-study/0.1 (public data research)"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_checksums() -> dict:
    if CHECKSUMS.exists():
        return json.loads(CHECKSUMS.read_text(encoding="utf-8"))
    return {}


def save_checksums(data: dict) -> None:
    CHECKSUMS.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def download(url: str, dest: Path, retries: int = 3) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as resp, dest.open("wb") as out:
                while block := resp.read(1 << 20):
                    out.write(block)
            return
        except OSError:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)


def fetch_all(update_checksums: bool = False) -> dict:
    """Download missing files, record checksums, fail on a changed file."""
    RAW.mkdir(parents=True, exist_ok=True)
    known = load_checksums()
    for src in sources():
        path = RAW / src["file"]
        if not path.exists():
            print(f"download {src['file']}")
            download(src["url"], path)
        digest = sha256_of(path)
        entry = known.get(src["file"])
        if entry and entry["sha256"] != digest and not update_checksums:
            raise SystemExit(
                f"checksum changed for {src['file']}: the Census Bureau may have "
                "republished it. Re-run with --update-checksums to accept."
            )
        known[src["file"]] = {
            "sha256": digest,
            "bytes": path.stat().st_size,
            "url": src["url"],
            "what": src["what"],
            "vintage": src["vintage"],
        }
    save_checksums(known)
    return known


if __name__ == "__main__":
    fetch_all("--update-checksums" in sys.argv)
