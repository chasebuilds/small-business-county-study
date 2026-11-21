"""Make-style entry point: python make.py <target>.

Targets
  fetch     download raw files into data/raw and verify checksums
  extract   cut raw files down to the small committed extracts
  charts    redraw every chart from the extracts
  report    rebuild docs/index.html
  build     charts + report (works offline from the committed extracts)
  all       fetch + extract + build
  test      ruff + pytest
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def fetch() -> None:
    from sbcs import fetch as f

    f.fetch_all("--update-checksums" in sys.argv)


def extract() -> None:
    from sbcs import extract as e

    e.run()


def charts() -> None:
    from sbcs import analysis
    from sbcs import charts as c

    paths = c.build_all(analysis.load(), ROOT / "docs" / "charts")
    print(f"wrote {len(paths)} charts")


def report() -> None:
    from sbcs import report as r

    print("wrote", r.build())


def build() -> None:
    charts()
    report()


def all_() -> None:
    fetch()
    extract()
    build()


def test() -> None:
    subprocess.run([sys.executable, "-m", "ruff", "check", "."], check=True, cwd=ROOT)
    subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True, cwd=ROOT)


TARGETS = {
    "fetch": fetch,
    "extract": extract,
    "charts": charts,
    "report": report,
    "build": build,
    "all": all_,
    "test": test,
}

if __name__ == "__main__":
    name = next((a for a in sys.argv[1:] if not a.startswith("--")), "build")
    if name not in TARGETS:
        raise SystemExit(f"unknown target {name!r}. choose from: {', '.join(TARGETS)}")
    TARGETS[name]()
