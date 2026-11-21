"""Pure cleaning and transform functions. No network, no file access.

County Business Patterns (CBP) notes that drive the rules here:

* ``est`` (establishment count) is always published.
* ``emp`` (employment) carries a noise flag. ``G``, ``H`` and ``J`` mean the value was
  published with noise of under 2%, 2% to under 5%, and 5% or more. The number is usable
  but approximate. ``D``, ``S`` and ``N`` (and in 2012 to 2016 files, a range letter in
  ``empflag``) mean the value was withheld, so it is treated as missing, never as zero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SUPPRESSED_FLAGS = {"D", "S", "N", "X", "Z"}
NOISE_FLAGS = {"G", "H", "J"}

SIZE_COLUMNS = [
    "n_lt5",
    "n5_9",
    "n10_19",
    "n20_49",
    "n50_99",
    "n100_249",
    "n250_499",
    "n500_999",
    "n1000",
]
SMALL_SIZE_COLUMNS = ["n_lt5", "n5_9", "n10_19"]  # fewer than 20 employees


def naics_clean(code: str) -> str:
    """'23----' -> '23', '236///' -> '236', '------' -> 'ALL'."""
    stripped = str(code).strip().rstrip("-/")
    return stripped if stripped else "ALL"


def naics_level(code: str) -> int:
    """Digits in a cleaned NAICS code; 0 for the all-sector total."""
    return 0 if code == "ALL" else len(code)


def fips5(state: str | int, county: str | int) -> str:
    return f"{int(state):02d}{int(county):03d}"


def emp_is_suppressed(flag: object, empflag: object = "") -> bool:
    """True when employment was withheld rather than published."""
    flag_text = "" if pd.isna(flag) else str(flag).strip().upper()
    range_text = "" if pd.isna(empflag) else str(empflag).strip()
    # Uppercase letters are employment size ranges (value withheld). A lowercase 'r'
    # only marks a revised figure and the number is real.
    return flag_text in SUPPRESSED_FLAGS or (range_text.isalpha() and range_text.isupper())


def clean_cbp(raw: pd.DataFrame, year: int, geo: str) -> pd.DataFrame:
    """Normalise one CBP file to: year, geo, fips, naics, est, emp, emp_flag, size bins.

    ``geo`` is ``county``, ``state`` or ``national``. National and state files hold one
    row per legal form of organisation, only the all-forms row (``lfo == '-'``) is kept.
    """
    df = raw.copy()
    if "lfo" in df.columns:
        df = df[df["lfo"].astype(str).str.strip() == "-"]
    df = df.rename(columns={"n<5": "n_lt5", "n1_4": "n_lt5"})
    if geo == "county":
        df["fips"] = [fips5(s, c) for s, c in zip(df["fipstate"], df["fipscty"], strict=True)]
    elif geo == "state":
        df["fips"] = [f"{int(s):02d}000" for s in df["fipstate"]]
    else:
        df["fips"] = "00000"
    empflag = df["empflag"] if "empflag" in df.columns else pd.Series("", index=df.index)
    emp_nf = df["emp_nf"] if "emp_nf" in df.columns else pd.Series("", index=df.index)
    suppressed = [emp_is_suppressed(a, b) for a, b in zip(emp_nf, empflag, strict=True)]
    out = pd.DataFrame(
        {
            "year": year,
            "geo": geo,
            "fips": df["fips"].to_numpy(),
            "naics": [naics_clean(c) for c in df["naics"]],
            "est": pd.to_numeric(df["est"], errors="coerce").to_numpy(),
            "emp": pd.to_numeric(df["emp"], errors="coerce").to_numpy(),
            "emp_flag": [
                "SUP" if s else (str(f).strip().upper() if pd.notna(f) else "")
                for s, f in zip(suppressed, emp_nf, strict=True)
            ],
        }
    )
    out.loc[out["emp_flag"] == "SUP", "emp"] = np.nan
    for col in SIZE_COLUMNS:
        out[col] = pd.to_numeric(df[col], errors="coerce").to_numpy() if col in df else np.nan
    return out.reset_index(drop=True)


def per_1000(count: pd.Series | float, population: pd.Series | float) -> pd.Series | float:
    """Count per 1,000 residents."""
    return count / population * 1000


def region_total(df: pd.DataFrame, col: str) -> float:
    """Sum a column across counties. Returns NaN if any county value is missing.

    A partial sum would silently understate the region, so missing values propagate.
    """
    values = df[col]
    return float("nan") if values.isna().any() else float(values.sum())


def region_by_naics(counties: pd.DataFrame) -> pd.DataFrame:
    """Combine county rows into one row per (year, naics) for the region.

    ``emp`` is the strict sum (NaN if any county withheld it), ``emp_missing`` counts how
    many counties withheld it, and ``est`` is always a complete sum.
    """
    rows = []
    for (year, naics), grp in counties.groupby(["year", "naics"], sort=True):
        row = {
            "year": year,
            "naics": naics,
            "est": float(grp["est"].sum()),
            "emp": region_total(grp, "emp"),
            "emp_missing": int(grp["emp"].isna().sum()),
            "counties": int(grp["fips"].nunique()),
        }
        for col in SIZE_COLUMNS:
            row[col] = float(grp[col].sum()) if grp[col].notna().all() else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def index_to_base(series: pd.Series, base_pos: int = 0) -> pd.Series:
    """Rescale so the base position equals 100."""
    base = series.iloc[base_pos]
    if pd.isna(base) or base == 0:
        return series * np.nan
    return series / base * 100


def small_share(row: pd.Series) -> float:
    """Share of establishments with fewer than 20 employees."""
    total = row["est"]
    small = sum(row[c] for c in SMALL_SIZE_COLUMNS)
    return float(small / total) if total and not np.isnan(small) else float("nan")


def parse_acs_table(lines: list[str]) -> pd.DataFrame:
    """Parse a pipe-delimited ACS table-based summary file body (header first)."""
    header = lines[0].strip().split("|")
    rows = [ln.rstrip("\n").split("|") for ln in lines[1:] if ln.strip()]
    df = pd.DataFrame(rows, columns=header)
    for col in header[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def geo_kind(geo_id: str) -> str:
    """Map an ACS GEO_ID prefix to county, state or national ('' if other)."""
    if geo_id.startswith("0500000US"):
        return "county"
    if geo_id.startswith("0400000US"):
        return "state"
    if geo_id == "0100000US":
        return "national"
    return ""


def geo_fips(geo_id: str) -> str:
    """'0500000US21195' -> '21195'; state -> '21000'; US -> '00000'."""
    kind = geo_kind(geo_id)
    if kind == "county":
        return geo_id[-5:]
    if kind == "state":
        return geo_id[-2:] + "000"
    return "00000"


def share(numerator: float, denominator: float) -> float:
    """Percent, NaN when the denominator is missing or zero."""
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return float("nan")
    return float(numerator / denominator * 100)


def income_unreliable(estimate: float, moe: float, threshold: float = 0.10) -> bool:
    """True when the margin of error is over ``threshold`` of the estimate."""
    if pd.isna(estimate) or pd.isna(moe) or estimate <= 0:
        return True
    return bool(moe / estimate > threshold)
